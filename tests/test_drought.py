"""Local Drought rules, with a regression guard for the anniversary bug:
landing on a Local Drought space exactly as the 44-space drought circuit
completes must EXTEND the drought (reset the clock), not force a second
half-stock sale."""
import pytest

from app import models
from app.constants import BOARD_SIZE
from app.services.turn_manager import TurnManager
from tests.conftest import total_sheep


LOCAL_DROUGHT_INDEX = 22


@pytest.fixture
def drought_board(session):
    """44 plain spaces except board_index 22, a Local Drought."""
    for n in range(BOARD_SIZE):
        session.add(models.Space(
            board_index=n, name=f"Space {n}",
            space_type=("local_drought" if n == LOCAL_DROUGHT_INDEX else "open"),
        ))
    session.commit()


def play_roll(session, game, d1, d2, monkeypatch):
    monkeypatch.setattr(TurnManager, "_roll_dice", staticmethod(lambda: (d1, d2)))
    TurnManager(session, game.game_id).play_turn()
    session.commit()


def test_anniversary_landing_extends_without_selling(session, game_factory, drought_board, monkeypatch):
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None)),
                     sheep_per_paddock=3, current="Hu")  # 15 natural pens
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    # Three spaces short of the drought space, with the clock about to expire
    # on exactly this move — the anniversary.
    hu.current_board_index = 19
    hu.is_in_drought = True
    hu.drought_start_space = LOCAL_DROUGHT_INDEX
    hu.drought_spaces_remaining = 3
    session.commit()
    pens_before = total_sheep(session, g.game_id, hu.game_player_id)

    play_roll(session, g, 1, 2, monkeypatch)  # 19 + 3 -> lands on 22

    session.refresh(hu)
    assert hu.current_board_index == LOCAL_DROUGHT_INDEX
    # No second sale.
    assert total_sheep(session, g.game_id, hu.game_player_id) == pens_before
    # Drought extended: still in drought, clock reset to a fresh circuit.
    assert hu.is_in_drought
    assert hu.drought_spaces_remaining == BOARD_SIZE
    # The modal reports an extension, not a fresh sale.
    pending = (session.query(models.PendingAction)
               .filter_by(game_id=g.game_id, action_type="drought_effect",
                          active_player_id=hu.game_player_id)
               .order_by(models.PendingAction.pending_action_id.desc()).first())
    import json
    data = json.loads(pending.action_data)
    assert data["extended"] is True
    assert data["pens_sold"] == 0


def test_still_in_drought_landing_extends_without_selling(session, game_factory, drought_board, monkeypatch):
    """Landing on the drought space while the clock is still running (not the
    anniversary) must also extend without selling — this already worked, kept
    as a guard."""
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None)),
                     sheep_per_paddock=3, current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 19
    hu.is_in_drought = True
    hu.drought_start_space = LOCAL_DROUGHT_INDEX
    hu.drought_spaces_remaining = 30  # plenty left
    session.commit()
    pens_before = total_sheep(session, g.game_id, hu.game_player_id)

    play_roll(session, g, 1, 2, monkeypatch)

    session.refresh(hu)
    assert total_sheep(session, g.game_id, hu.game_player_id) == pens_before
    assert hu.is_in_drought
    assert hu.drought_spaces_remaining == BOARD_SIZE  # reset by extension


def test_fresh_drought_landing_sells_half(session, game_factory, drought_board, monkeypatch):
    """The normal case must still sell: a player NOT in drought who lands on
    the Local Drought space sells half their Natural/Improved stock."""
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None)),
                     sheep_per_paddock=3, current="Hu")  # 15 pens
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 19
    hu.is_in_drought = False
    session.commit()
    pens_before = total_sheep(session, g.game_id, hu.game_player_id)

    play_roll(session, g, 1, 2, monkeypatch)

    session.refresh(hu)
    # Half of 15, rounded up = 8 sold, 7 remain.
    sold = pens_before - total_sheep(session, g.game_id, hu.game_player_id)
    assert sold == 8
    assert hu.is_in_drought
    assert hu.drought_spaces_remaining == BOARD_SIZE
