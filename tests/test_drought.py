"""Local Drought rules under "Max's rule" (no extension): a drought lasts
exactly one 44-space circuit and is never extended. Landing on Local Drought
again (or at the circuit anniversary), or drawing a drought card while in
drought, has no effect; the original clock runs out and the restriction ends.
A fresh landing once free triggers a new drought normally."""
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


def test_anniversary_landing_ends_drought_no_sale(session, game_factory, drought_board, monkeypatch):
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
    # Max's rule: the circuit completed this move, so the drought ENDS — it is
    # not re-triggered or extended by landing on the space again.
    assert not hu.is_in_drought
    assert hu.drought_spaces_remaining == 0
    pending = (session.query(models.PendingAction)
               .filter_by(game_id=g.game_id, action_type="drought_effect",
                          active_player_id=hu.game_player_id)
               .order_by(models.PendingAction.pending_action_id.desc()).first())
    import json
    data = json.loads(pending.action_data)
    assert data["extended"] is False
    assert data["pens_sold"] == 0
    assert data["no_effect"] is True


def test_still_in_drought_landing_is_not_extended(session, game_factory, drought_board, monkeypatch):
    """Max's rule: landing on the drought space while still in drought has no
    effect and does NOT reset the clock — the original circuit keeps counting
    down."""
    g = game_factory(players=(("Hu", False, None), ("Bo", False, None)),
                     sheep_per_paddock=3, current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 19
    hu.is_in_drought = True
    hu.drought_start_space = LOCAL_DROUGHT_INDEX
    hu.drought_spaces_remaining = 30  # plenty left
    session.commit()
    pens_before = total_sheep(session, g.game_id, hu.game_player_id)

    play_roll(session, g, 1, 2, monkeypatch)  # moves 3 spaces

    session.refresh(hu)
    assert total_sheep(session, g.game_id, hu.game_player_id) == pens_before
    assert hu.is_in_drought
    # Clock keeps counting down from 30 (−3), NOT reset to a fresh circuit.
    assert hu.drought_spaces_remaining == 27


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


def test_drought_card_while_in_drought_has_no_effect(session, game_factory, drought_board, monkeypatch):
    """A Local Drought Tucker Bag card drawn while already in drought is a
    no-op: no sale, and the clock is not extended."""
    from app.services.card_service import CardService
    g = game_factory(sheep_per_paddock=3, paddock_type="natural", current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.is_in_drought = True
    hu.drought_start_space = LOCAL_DROUGHT_INDEX
    hu.drought_spaces_remaining = 20
    session.commit()
    pens_before = total_sheep(session, g.game_id, hu.game_player_id)
    turn = models.Turn(game_id=g.game_id, turn_number=1,
                       active_game_player_id=hu.game_player_id, dice_roll_1=1, dice_roll_2=1)
    session.add(turn); session.flush()

    result = CardService(session, g.game_id)._effect_drought_local(hu, {}, turn.turn_id)

    session.refresh(hu)
    assert result["no_effect"] is True and result["extended"] is False
    assert total_sheep(session, g.game_id, hu.game_player_id) == pens_before
    assert hu.drought_spaces_remaining == 20  # untouched


def test_bore_while_already_blocked_has_no_effect(session, game_factory, monkeypatch):
    """Landing on Bore Dries Up while still under a bore restriction is a
    no-op: no sale, and the restock block is not extended."""
    from app.constants import BOARD_SIZE as BSZ
    # Board with a Bore Dries Up space at index 5.
    for n in range(BSZ):
        session.add(models.Space(board_index=n, name=f"S{n}",
                                 space_type=("bore_dries_up" if n == 5 else "open")))
    session.commit()
    g = game_factory(sheep_per_paddock=3, paddock_type="irrigated", current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 2
    hu.bore_dried_up = True
    hu.restock_blocked_until_circuit = True
    hu.restock_block_scope = "irrigated"
    hu.restock_block_spaces_remaining = 25
    session.commit()
    pens_before = total_sheep(session, g.game_id, hu.game_player_id)

    play_roll(session, g, 1, 2, monkeypatch)  # land on 5 (bore)

    session.refresh(hu)
    assert total_sheep(session, g.game_id, hu.game_player_id) == pens_before
    # Block not reset: 25 − 3 = 22, still counting down the original circuit.
    assert hu.restock_block_spaces_remaining == 22
