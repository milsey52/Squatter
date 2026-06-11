"""Shared test fixtures.

DATABASE_URL is forced to a throwaway SQLite file BEFORE any app module is
imported, so the suite can never touch a real database. SQLite ignores
FOR UPDATE locks — concurrency is exercised behaviourally here (state
mutations injected mid-action); the lock mechanism itself needs Postgres.

Run with ./run_tests.sh (system python3 is too old for this codebase —
it needs 3.10+).
"""
import json
import os
import tempfile

_db_fd, _db_path = tempfile.mkstemp(prefix="squatter_test_", suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ.pop("ADMIN_SECRET", None)

import pytest

from app.db import Base, engine
from app.db import SessionLocal as _SessionLocal
from app import models


@pytest.fixture(autouse=True)
def fresh_db():
    """Brand-new schema per test — no cross-test state."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    s = _SessionLocal()
    yield s
    s.close()


@pytest.fixture
def spaces(session):
    """A 44-space board of plain spaces (no special handlers fire)."""
    for n in range(44):
        session.add(models.Space(board_index=n, name=f"Space {n}", space_type="open"))
    session.commit()


class GameHandle:
    """What game_factory returns: ids for direct assertions."""

    def __init__(self, game_id, players):
        self.game_id = game_id
        self.players = players  # name -> game_player_id


@pytest.fixture
def game_factory(session):
    """Create an in-progress game with paddocks, rules and players.

    players: sequence of (name, is_ai, difficulty). Humans get their own
    User row (mirroring per-game identity in the lobby routes).
    """
    def _make(*, starting_cash=2000,
              players=(("Hu", False, None), ("Jim", True, "medium")),
              sheep_per_paddock=3, paddock_type="natural",
              current=None, status="in_progress"):
        host_user = models.User(display_name=players[0][0])
        session.add(host_user)
        session.flush()
        game = models.Game(
            host_user_id=host_user.user_id,
            game_code=f"T{host_user.user_id % 100000:05d}",
            status=status,
        )
        session.add(game)
        session.flush()
        session.add(models.GameRule(
            game_id=game.game_id,
            starting_cash=starting_cash,
            ai_reaction_time_seconds=1,
        ))
        ids = {}
        for order, (name, is_ai, diff) in enumerate(players, start=1):
            if is_ai:
                user_id = None
            elif order == 1:
                user_id = host_user.user_id
            else:
                u = models.User(display_name=name)
                session.add(u)
                session.flush()
                user_id = u.user_id
            gp = models.GamePlayer(
                game_id=game.game_id,
                user_id=user_id,
                player_name=name,
                turn_order=order,
                current_space_id=0,
                is_ai=is_ai,
                ai_difficulty=diff,
            )
            session.add(gp)
            session.flush()
            ids[name] = gp.game_player_id
            for n in range(1, 6):
                session.add(models.Paddock(
                    game_id=game.game_id,
                    owner_game_player_id=gp.game_player_id,
                    paddock_number=n,
                    paddock_type=paddock_type,
                    sheep_pens=sheep_per_paddock,
                    max_pens=3,
                ))
        current_name = current or players[0][0]
        game.current_game_player_id = ids[current_name]
        session.commit()
        return GameHandle(game.game_id, ids)

    return _make


@pytest.fixture
def stock_sale_pending(session):
    """Put a player on a Stock Sale decision, optionally frozen mid-commit
    (card already drawn at lock_price, committed_pens locked in)."""
    def _make(game_id, player_id, *, card_prices=(400,),
              lock_price=None, committed_pens=None, in_drought=False,
              empty_pens=15, total_pens=0):
        cards = []
        for bp in card_prices:
            c = models.StockCard(
                buy_price_per_pen=bp,
                sell_price_natural=bp + 100,
                sell_price_improved_irrigated=bp + 150,
            )
            session.add(c)
            cards.append(c)
        session.flush()
        turn = models.Turn(game_id=game_id, turn_number=1,
                           active_game_player_id=player_id,
                           dice_roll_1=3, dice_roll_2=4)
        session.add(turn)
        session.flush()
        data = {
            "space_name": "Stock Sale", "in_drought": in_drought,
            "total_pens": total_pens, "empty_pens": empty_pens,
            "empty_irrigated_pens": 0, "max_per_transaction": 15,
            "restock_blocked": False, "restock_block_scope": None,
            "natural_pens": total_pens, "improved_pens": 0, "irrigated_pens": 0,
            "next_sell_price_modifier": 0,
        }
        if lock_price is not None:
            locked = next(c for c in cards if c.buy_price_per_pen == lock_price)
            session.add(models.StockCardDraw(
                game_id=game_id, turn_id=turn.turn_id,
                stock_card_id=locked.stock_card_id, draw_order=1,
            ))
            data.update({"buy_committed": True,
                         "original_pens": committed_pens, "hsp_locked": False})
        pending = models.PendingAction(
            game_id=game_id, turn_id=turn.turn_id,
            action_type="stock_sale_decision",
            active_player_id=player_id,
            action_data=json.dumps(data),
        )
        session.add(pending)
        session.commit()
        return pending

    return _make


def drain_cash(session, game_id, player_id, amount):
    """Move cash from a player to the bank outside normal game flow."""
    session.add(models.Transaction(
        game_id=game_id, player_from_id=player_id, player_to_id=None,
        amount=amount, transaction_type="test_adjustment",
    ))
    session.commit()


def total_sheep(session, game_id, player_id=None):
    q = session.query(models.Paddock).filter_by(game_id=game_id)
    if player_id is not None:
        q = q.filter_by(owner_game_player_id=player_id)
    return sum(p.sheep_pens for p in q)
