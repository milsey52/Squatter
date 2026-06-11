"""Stock Sale decision rules: commit-then-reveal, soft insufficient funds,
reduce-only retries, no switching to sell after a buy commit."""
import pytest

from app import models
from app.services.decision_service import DecisionService
from app.services.ledger_service import LedgerService
from tests.conftest import total_sheep


@pytest.fixture
def game(game_factory):
    # Empty paddocks: 15 pens of capacity, 0 sheep.
    return game_factory(sheep_per_paddock=0, starting_cash=2800, current="Jim")


def test_buy_pays_stocks_and_resolves(session, game, stock_sale_pending):
    jim = game.players["Jim"]
    pending = stock_sale_pending(game.game_id, jim, card_prices=(400,))
    result = DecisionService(session, game.game_id).stock_sale_buy(jim, 5)
    session.commit()
    assert result["status"] == "bought"
    assert result["total_cost"] == 2000
    assert total_sheep(session, game.game_id, jim) == 5
    assert LedgerService(session, game.game_id).player_balance(jim) == 800
    assert pending.resolved_at is not None
    # A result modal pending is queued for acknowledgement.
    assert session.query(models.PendingAction).filter_by(
        game_id=game.game_id, resolved_at=None).count() == 1


def test_insufficient_funds_is_soft_with_price_info(session, game, stock_sale_pending):
    jim = game.players["Jim"]
    pending = stock_sale_pending(game.game_id, jim, card_prices=(400,))
    result = DecisionService(session, game.game_id).stock_sale_buy(jim, 8)  # 8x400 > 2800
    assert result["status"] == "insufficient_funds"
    assert result["buy_price"] == 400
    assert result["max_affordable_pens"] == 7
    assert pending.resolved_at is None  # stays open for retry
    assert total_sheep(session, game.game_id, jim) == 0


def test_retry_may_only_reduce_the_commitment(session, game, stock_sale_pending):
    jim = game.players["Jim"]
    stock_sale_pending(game.game_id, jim, card_prices=(400,),
                       lock_price=400, committed_pens=5)
    service = DecisionService(session, game.game_id)
    with pytest.raises(ValueError, match="5 or fewer"):
        service.stock_sale_buy(jim, 6)
    assert service.stock_sale_buy(jim, 3)["status"] == "bought"


def test_cannot_switch_to_sell_after_buy_commit(session, game, stock_sale_pending):
    jim = game.players["Jim"]
    stock_sale_pending(game.game_id, jim, card_prices=(400,),
                       lock_price=400, committed_pens=8)
    with pytest.raises(ValueError, match="committed to buy"):
        DecisionService(session, game.game_id).stock_sale_sell(jim, pens=2)


def test_pass_resolves_even_after_commit(session, game, stock_sale_pending):
    """A player who committed but cannot afford the locked price must
    always have the pass exit — this is what prevents a frozen game."""
    jim = game.players["Jim"]
    pending = stock_sale_pending(game.game_id, jim, card_prices=(400,),
                                 lock_price=400, committed_pens=8)
    result = DecisionService(session, game.game_id).stock_sale_pass(jim)
    assert result["status"] == "passed"
    assert pending.resolved_at is not None


def test_sell_credits_income_and_removes_sheep(session, game_factory, stock_sale_pending):
    g = game_factory(sheep_per_paddock=3, starting_cash=2000, current="Jim")
    jim = g.players["Jim"]
    pending = stock_sale_pending(g.game_id, jim, card_prices=(400,), total_pens=15)
    result = DecisionService(session, g.game_id).stock_sale_sell(
        jim, pens=4, pens_by_type={"natural": 4, "improved": 0, "irrigated": 0})
    session.commit()
    # Card: buy 400 -> sell_natural 500.
    assert result["total_income"] == 4 * 500
    assert total_sheep(session, g.game_id, jim) == 11
    assert LedgerService(session, g.game_id).player_balance(jim) == 4000
    assert pending.resolved_at is not None


def test_wrong_player_cannot_act_on_pending(session, game, stock_sale_pending):
    stock_sale_pending(game.game_id, game.players["Jim"])
    with pytest.raises(ValueError, match="Not this player's decision"):
        DecisionService(session, game.game_id).stock_sale_buy(game.players["Hu"], 1)
