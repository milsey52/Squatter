"""LedgerService: cash is derived from the transaction log, never stored."""
import pytest

from app import models
from app.services.ledger_service import LedgerService


@pytest.fixture
def game(game_factory):
    return game_factory(starting_cash=2000)


def test_starting_balance_is_starting_cash(session, game):
    ledger = LedgerService(session, game.game_id)
    assert ledger.player_balance(game.players["Hu"]) == 2000
    assert ledger.player_balance(game.players["Jim"]) == 2000


def test_bank_payment_and_reward(session, game):
    ledger = LedgerService(session, game.game_id)
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    ledger.pay_bank(hu, 300, "expense", None)
    assert ledger.player_balance(hu.game_player_id) == 1700
    ledger.receive_from_bank(hu, 500, "wool_cheque", None)
    assert ledger.player_balance(hu.game_player_id) == 2200


def test_player_to_player_transfer(session, game):
    ledger = LedgerService(session, game.game_id)
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    jim = session.query(models.GamePlayer).get(game.players["Jim"])
    ledger.pay_player(hu, jim, 450, "stud_fee", None)
    assert ledger.player_balance(hu.game_player_id) == 1550
    assert ledger.player_balance(jim.game_player_id) == 2450


def test_non_positive_amount_rejected(session, game):
    ledger = LedgerService(session, game.game_id)
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    with pytest.raises(ValueError):
        ledger.pay_bank(hu, 0, "expense", None)
    with pytest.raises(ValueError):
        ledger.pay_bank(hu, -50, "expense", None)


def test_sequence_in_turn_increments(session, game):
    ledger = LedgerService(session, game.game_id)
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    turn = models.Turn(game_id=game.game_id, turn_number=1,
                       active_game_player_id=hu.game_player_id,
                       dice_roll_1=1, dice_roll_2=2)
    session.add(turn)
    session.flush()
    t1 = ledger.pay_bank(hu, 100, "expense", turn.turn_id)
    t2 = ledger.pay_bank(hu, 100, "expense", turn.turn_id)
    assert (t1.sequence_in_turn, t2.sequence_in_turn) == (1, 2)


def test_balances_are_per_game(session, game_factory):
    g1 = game_factory(starting_cash=2000)
    g2 = game_factory(starting_cash=1000)
    hu1 = session.query(models.GamePlayer).get(g1.players["Hu"])
    LedgerService(session, g1.game_id).pay_bank(hu1, 700, "expense", None)
    assert LedgerService(session, g1.game_id).player_balance(g1.players["Hu"]) == 1300
    assert LedgerService(session, g2.game_id).player_balance(g2.players["Hu"]) == 1000
