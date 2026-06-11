"""AI Stock Sale behaviour: affordability before commit, cash cushion,
recovery after the price reveal. Regression suite for the BEC1YA freeze
(AI committed to 8 pens with $2800, then re-requested the same quantity
every tick forever)."""
import pytest

from app import models
from app.services.ai_service import AIPlayerService
from app.services.ledger_service import LedgerService
from tests.conftest import total_sheep


def handle(session, game, name, pending):
    player = session.query(models.GamePlayer).get(game.players[name])
    tag = AIPlayerService(session, game.game_id, player).handle_pending(pending)
    session.flush()
    return tag


def balance(session, game, name):
    return LedgerService(session, game.game_id).player_balance(game.players[name])


# ── Medium: cushion is $500 ─────────────────────────────────────────────

def test_medium_clamps_commit_to_best_case_price(session, game_factory, stock_sale_pending):
    g = game_factory(sheep_per_paddock=0, starting_cash=2800, current="Jim")
    pending = stock_sale_pending(g.game_id, g.players["Jim"], card_prices=(400,))
    tag = handle(session, g, "Jim", pending)
    # spendable (2800-500) // 400 = 5 pens, keeps $800.
    assert tag == "stock_sale:bought_5"
    assert balance(session, g, "Jim") == 800
    assert pending.resolved_at is not None


def test_medium_reduces_when_locked_price_exceeds_best_case(session, game_factory, stock_sale_pending):
    """The frozen-game shape: committed 8, locked card pricier than hoped."""
    g = game_factory(sheep_per_paddock=0, starting_cash=2800, current="Jim")
    pending = stock_sale_pending(g.game_id, g.players["Jim"],
                                 card_prices=(400, 700),
                                 lock_price=700, committed_pens=8)
    tag = handle(session, g, "Jim", pending)
    # spendable 2300 // 700 = 3 pens, keeps $700.
    assert tag == "stock_sale:bought_3_reduced"
    assert total_sheep(session, g.game_id, g.players["Jim"]) == 3
    assert pending.resolved_at is not None


def test_frozen_commit_resolves_even_when_broke(session, game_factory, stock_sale_pending):
    """Committed to buy but cannot afford a single pen: must still resolve."""
    g = game_factory(sheep_per_paddock=0, starting_cash=300, current="Jim")
    pending = stock_sale_pending(g.game_id, g.players["Jim"],
                                 card_prices=(400,),
                                 lock_price=400, committed_pens=8)
    handle(session, g, "Jim", pending)
    assert pending.resolved_at is not None
    assert total_sheep(session, g.game_id, g.players["Jim"]) == 0


def test_cushion_blocks_buy_when_cash_is_tight(session, game_factory, stock_sale_pending):
    # $700 cash, 15 pens (not "stuck"): spendable $200 buys nothing at $400.
    g = game_factory(sheep_per_paddock=0, starting_cash=700, current="Jim")
    pending = stock_sale_pending(g.game_id, g.players["Jim"], card_prices=(400,))
    tag = handle(session, g, "Jim", pending)
    assert tag == "stock_sale:passed"
    assert balance(session, g, "Jim") == 700


def test_stuck_recovery_waives_the_cushion(session, game_factory, stock_sale_pending):
    # 0 pens + $500 cash = stuck: reserve waived, buys 1 pen at $400.
    g = game_factory(sheep_per_paddock=0, starting_cash=500, current="Jim")
    pending = stock_sale_pending(g.game_id, g.players["Jim"], card_prices=(400,))
    tag = handle(session, g, "Jim", pending)
    assert tag == "stock_sale:bought_1"
    assert total_sheep(session, g.game_id, g.players["Jim"]) == 1


# ── Hard: cushion is $250, plus drought-imminent buffer ─────────────────

def hard_game(game_factory, space):
    def _factory(**kw):
        return game_factory(players=(("Hu", False, None), ("Hardy", True, "hard")),
                            current="Hardy", **kw)
    return _factory


def test_hard_reserve_without_drought_ahead(session, game_factory, stock_sale_pending):
    g = game_factory(players=(("Hu", False, None), ("Hardy", True, "hard")),
                     sheep_per_paddock=0, starting_cash=2800, current="Hardy")
    # Space 0: Local Drought spaces (22, 43) are beyond the 10-space lookahead.
    pending = stock_sale_pending(g.game_id, g.players["Hardy"], card_prices=(700,))
    tag = handle(session, g, "Hardy", pending)
    # spendable (2800-250) // 700 = 3 pens.
    assert tag == "stock_sale:bought_3"
    assert balance(session, g, "Hardy") == 700


def test_hard_adds_drought_buffer_when_drought_imminent(session, game_factory, stock_sale_pending):
    g = game_factory(players=(("Hu", False, None), ("Hardy", True, "hard")),
                     sheep_per_paddock=0, starting_cash=2800, current="Hardy")
    hardy = session.query(models.GamePlayer).get(g.players["Hardy"])
    hardy.current_board_index = 15  # Local Drought at 22 is within lookahead
    session.commit()
    pending = stock_sale_pending(g.game_id, g.players["Hardy"], card_prices=(700,))
    tag = handle(session, g, "Hardy", pending)
    # spendable (2800-250-500) // 700 = 2 pens.
    assert tag == "stock_sale:bought_2"
    assert balance(session, g, "Hardy") == 1400


# ── Medium: defensive behaviours ────────────────────────────────────────

def test_medium_passes_during_drought(session, game_factory, stock_sale_pending):
    g = game_factory(sheep_per_paddock=0, starting_cash=2800, current="Jim")
    pending = stock_sale_pending(g.game_id, g.players["Jim"],
                                 card_prices=(400,), in_drought=True)
    tag = handle(session, g, "Jim", pending)
    assert tag == "stock_sale:passed_drought"
    assert pending.resolved_at is not None
