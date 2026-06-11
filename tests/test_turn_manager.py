"""TurnManager: dice, movement, rotation, and per-move state bookkeeping."""
import pytest

from app import models
from app.services.turn_manager import TurnManager


@pytest.fixture
def game(game_factory, spaces):
    return game_factory(current="Hu")


def play(session, game, dice, monkeypatch):
    monkeypatch.setattr(TurnManager, "_roll_dice", staticmethod(lambda: dice))
    TurnManager(session, game.game_id).play_turn()
    session.commit()


def current_player_id(session, game):
    return session.query(models.Game).get(game.game_id).current_game_player_id


def test_turn_moves_player_and_advances_rotation(session, game, monkeypatch):
    play(session, game, (2, 3), monkeypatch)
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    assert hu.current_board_index == 5
    turn = session.query(models.Turn).filter_by(game_id=game.game_id).one()
    assert (turn.dice_roll_1, turn.dice_roll_2) == (2, 3)
    assert turn.active_game_player_id == game.players["Hu"]
    # Rotation: Jim is up next.
    assert current_player_id(session, game) == game.players["Jim"]


def test_doubles_do_not_grant_extra_turn(session, game, monkeypatch):
    """Squatter manual p.4: doubles do NOT entitle a second throw."""
    play(session, game, (4, 4), monkeypatch)
    turn = session.query(models.Turn).filter_by(game_id=game.game_id).one()
    assert turn.is_double
    assert current_player_id(session, game) == game.players["Jim"]


def test_passing_start_wraps_and_pays_wool_cheque(session, game, monkeypatch):
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    hu.current_board_index = 40
    session.commit()
    play(session, game, (3, 3), monkeypatch)
    session.refresh(hu)
    assert hu.current_board_index == 2  # (40 + 6) % 44
    movement = session.query(models.Movement).filter_by(
        game_player_id=hu.game_player_id).one()
    assert movement.passed_start
    # Wool cheque: 15 pens (5 paddocks x 3) at $250/pen on top of $2000.
    from app.services.ledger_service import LedgerService
    assert LedgerService(session, game.game_id).player_balance(
        hu.game_player_id) == 2000 + 15 * 250
    pending = session.query(models.PendingAction).filter_by(
        game_id=game.game_id, action_type="wool_cheque_paid").one()
    assert pending.active_player_id == hu.game_player_id


def test_visiting_town_skips_roll_and_decrements(session, game, monkeypatch):
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    hu.visiting_town_turns = 2
    session.commit()
    play(session, game, (6, 6), monkeypatch)  # dice must be ignored
    session.refresh(hu)
    assert hu.visiting_town_turns == 1
    assert hu.current_board_index == 0  # did not move
    turn = session.query(models.Turn).filter_by(game_id=game.game_id).one()
    assert (turn.dice_roll_1, turn.dice_roll_2) == (0, 0)
    assert current_player_id(session, game) == game.players["Jim"]


def test_restock_block_decrements_and_clears(session, game, monkeypatch):
    hu = session.query(models.GamePlayer).get(game.players["Hu"])
    hu.restock_blocked_until_circuit = True
    hu.restock_block_spaces_remaining = 10
    hu.restock_block_scope = "all"
    hu.restock_block_source = "lucerne_flea"
    session.commit()

    play(session, game, (2, 2), monkeypatch)
    session.refresh(hu)
    assert hu.restock_blocked_until_circuit
    assert hu.restock_block_spaces_remaining == 6

    # Make it Hu's turn again and exhaust the counter.
    session.query(models.Game).get(game.game_id).current_game_player_id = hu.game_player_id
    session.commit()
    play(session, game, (3, 4), monkeypatch)
    session.refresh(hu)
    assert not hu.restock_blocked_until_circuit
    assert hu.restock_block_spaces_remaining == 0
    assert hu.restock_block_scope is None
    assert hu.restock_block_source is None
