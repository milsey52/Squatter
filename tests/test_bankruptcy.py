"""Debt and bankruptcy: a negative balance blocks rolling until the player
liquidates; debt beyond full liquidation value eliminates the player; the
last active player standing wins."""
import asyncio
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from app import models
from app.db import SessionLocal
from app.services import ai_autopilot
from app.services.bankruptcy_service import BankruptcyService, InDebtError
from app.services.ledger_service import LedgerService
from app.services.turn_manager import TurnManager
from tests.conftest import drain_cash, total_sheep


def mortgage_all(session, game, name, leave=0):
    paddocks = (
        session.query(models.Paddock)
        .filter_by(game_id=game.game_id, owner_game_player_id=game.players[name])
        .order_by(models.Paddock.paddock_number)
        .all()
    )
    for p in paddocks[leave:]:
        p.is_mortgaged = True
    session.commit()


# ── Liquidation arithmetic ──────────────────────────────────────────────

def test_liquidation_value_counts_all_assets(session, game_factory):
    g = game_factory(sheep_per_paddock=2)  # 10 pens, 5 unmortgaged natural
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.has_haystack = True
    session.commit()
    bk = BankruptcyService(session, g.game_id)
    # 10 pens x $400 + 5 x $100 mortgage + $350 haystack
    assert bk.liquidation_value(g.players["Jim"]) == 4000 + 500 + 350


def test_recovery_boundary(session, game_factory):
    g = game_factory(sheep_per_paddock=0)
    mortgage_all(session, g, "Jim", leave=1)  # one $100 natural mortgage left
    bk = BankruptcyService(session, g.game_id)
    drain_cash(session, g.game_id, g.players["Jim"], 2100)  # balance -100
    assert bk.can_recover(g.players["Jim"])      # -100 + 100 == 0
    drain_cash(session, g.game_id, g.players["Jim"], 100)   # balance -200
    assert not bk.can_recover(g.players["Jim"])  # -200 + 100 < 0


# ── play_turn debt checkpoint ───────────────────────────────────────────

def test_recoverable_debt_blocks_the_roll(session, game_factory):
    g = game_factory(current="Jim")  # 15 pens of sheep = plenty to liquidate
    drain_cash(session, g.game_id, g.players["Jim"], 2700)  # balance -700
    with pytest.raises(InDebtError):
        TurnManager(session, g.game_id).play_turn()
    assert session.query(models.Turn).filter_by(game_id=g.game_id).count() == 0
    assert session.query(models.GamePlayer).get(g.players["Jim"]).is_active


def test_unrecoverable_debt_eliminates_player(session, game_factory):
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None),
                              ("Jim", True, "medium")),
                     sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 2600)  # balance -600, nothing left
    # An open pending on Jim must not outlive him.
    turn0 = models.Turn(game_id=g.game_id, turn_number=0,
                        active_game_player_id=g.players["Jim"],
                        dice_roll_1=1, dice_roll_2=1)
    session.add(turn0)
    session.flush()
    stale = models.PendingAction(
        game_id=g.game_id, turn_id=turn0.turn_id, action_type="expense_payment",
        active_player_id=g.players["Jim"], action_data=json.dumps({}))
    session.add(stale)
    session.commit()

    TurnManager(session, g.game_id).play_turn()
    session.commit()

    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    assert not jim.is_active
    assert stale.resolved_at is not None
    # Turn passed to the next active player; game continues (2 left).
    game = session.query(models.Game).get(g.game_id)
    assert game.current_game_player_id == g.players["Hu"]
    assert game.status == "in_progress"
    # The bankruptcy itself is recorded as a no-roll turn.
    bankrupt_turn = (session.query(models.Turn)
                     .filter_by(game_id=g.game_id, active_game_player_id=g.players["Jim"])
                     .order_by(models.Turn.turn_id.desc()).first())
    assert (bankrupt_turn.dice_roll_1, bankrupt_turn.dice_roll_2) == (0, 0)


def test_last_player_standing_wins(session, game_factory):
    g = game_factory(sheep_per_paddock=0, current="Jim")  # Hu + Jim
    mortgage_all(session, g, "Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 2600)

    TurnManager(session, g.game_id).play_turn()
    session.commit()

    game = session.query(models.Game).get(g.game_id)
    assert game.status == "completed"
    won = session.query(models.PendingAction).filter_by(
        game_id=g.game_id, action_type="game_won").one()
    data = json.loads(won.action_data)
    assert data["winner_id"] == g.players["Hu"]
    assert data["reason"] == "last_player_standing"


# ── HTTP route ──────────────────────────────────────────────────────────

def test_route_refuses_roll_with_debt_guidance(session, game_factory):
    g = game_factory(current="Hu")
    drain_cash(session, g.game_id, g.players["Hu"], 2500)  # balance -500
    token = "debt-test-token"
    session.add(models.GameSession(
        session_token=token, user_id=session.query(models.GamePlayer).get(
            g.players["Hu"]).user_id,
        game_id=g.game_id, expires_at=datetime.now() + timedelta(days=1)))
    session.commit()
    client = TestClient(main.app)
    r = client.post(f"/games/{g.game_id}/turns",
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "$500 in debt" in r.json()["detail"]
    assert session.query(models.GamePlayer).get(g.players["Hu"]).is_active


# ── Autopilot debt recovery ─────────────────────────────────────────────

def drive(game_id, monkeypatch):
    async def no_sleep(_delay):
        pass
    monkeypatch.setattr(ai_autopilot.asyncio, "sleep", no_sleep)
    asyncio.run(ai_autopilot._drive_one_game(game_id))


def test_ai_sells_just_enough_sheep_to_clear_debt(session, game_factory, monkeypatch):
    g = game_factory(sheep_per_paddock=3, current="Jim")  # 15 pens: no mortgage rule
    drain_cash(session, g.game_id, g.players["Jim"], 2700)  # balance -700
    drive(g.game_id, monkeypatch)
    session.expire_all()
    # ceil(700/400) = 2 pens sold -> balance +100
    assert total_sheep(session, g.game_id, g.players["Jim"]) == 13
    assert LedgerService(session, g.game_id).player_balance(g.players["Jim"]) == 100
    assert session.query(models.GamePlayer).get(g.players["Jim"]).is_active


def test_ai_sells_haystack_when_no_sheep_or_paddocks(session, game_factory, monkeypatch):
    g = game_factory(sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.has_haystack = True
    session.commit()
    drain_cash(session, g.game_id, g.players["Jim"], 2200)  # balance -200
    drive(g.game_id, monkeypatch)
    session.expire_all()
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    assert not jim.has_haystack
    assert LedgerService(session, g.game_id).player_balance(g.players["Jim"]) == 150
    assert jim.is_active


def test_ai_with_nothing_left_goes_bankrupt_via_autopilot(session, game_factory, monkeypatch):
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None),
                              ("Jim", True, "medium")),
                     sheep_per_paddock=0, current="Jim")
    mortgage_all(session, g, "Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 2600)
    drive(g.game_id, monkeypatch)
    session.expire_all()
    assert not session.query(models.GamePlayer).get(g.players["Jim"]).is_active
    game = session.query(models.Game).get(g.game_id)
    assert game.current_game_player_id == g.players["Hu"]
    assert game.status == "in_progress"
