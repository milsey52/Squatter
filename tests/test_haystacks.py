"""Two hazard-keyed haystacks ("Max's rule"): a pasture haystack offsets
Local Drought (Natural/Improved); an irrigated haystack offsets Bore Dries
Up (Irrigated). Each is offered only to a player whose pasture is exposed to
that hazard, consumed only by its own hazard, and both burn in a fire."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from app import models
from app.constants import BOARD_SIZE
from app.services.station_service import StationService
from app.services.turn_manager import TurnManager


LOCAL_DROUGHT_INDEX = 22
BORE_INDEX = 5


@pytest.fixture
def hazard_board(session):
    for n in range(BOARD_SIZE):
        stype = "open"
        if n == LOCAL_DROUGHT_INDEX:
            stype = "local_drought"
        elif n == BORE_INDEX:
            stype = "bore_dries_up"
        session.add(models.Space(board_index=n, name=f"S{n}", space_type=stype))
    # A stock card for the haystack-offset draw on Local Drought.
    session.add(models.StockCard(buy_price_per_pen=400, sell_price_natural=500,
                                 sell_price_improved_irrigated=600))
    session.commit()


def play_roll(session, game, d1, d2, monkeypatch):
    monkeypatch.setattr(TurnManager, "_roll_dice", staticmethod(lambda: (d1, d2)))
    TurnManager(session, game.game_id).play_turn()
    session.commit()


# ── Offer logic ─────────────────────────────────────────────────────────

def test_offers_only_useful_types(session, game_factory):
    # Mixed station (natural by default) — owns Natural/Improved only.
    g = game_factory(sheep_per_paddock=1, paddock_type="natural")
    st = StationService(session, g.game_id)
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    types = {o["type"] for o in st.useful_haystack_offers(jim)}
    assert types == {"pasture"}

    # All-irrigated station → only the irrigated haystack is useful.
    g2 = game_factory(sheep_per_paddock=1, paddock_type="irrigated")
    st2 = StationService(session, g2.game_id)
    jim2 = session.query(models.GamePlayer).get(g2.players["Jim"])
    assert {o["type"] for o in st2.useful_haystack_offers(jim2)} == {"irrigated"}

    # Already holding the pasture haystack → no longer offered.
    jim.haystack_pasture = True
    session.commit()
    assert st.useful_haystack_offers(jim) == []


def test_mixed_station_offered_both(session, game_factory):
    g = game_factory(sheep_per_paddock=1, paddock_type="natural")
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    # Make one paddock irrigated so the player is exposed to both hazards.
    pad = session.query(models.Paddock).filter_by(
        game_id=g.game_id, owner_game_player_id=jim.game_player_id).first()
    pad.paddock_type = "irrigated"
    session.commit()
    types = {o["type"] for o in StationService(session, g.game_id).useful_haystack_offers(jim)}
    assert types == {"pasture", "irrigated"}


# ── Selective consumption ────────────────────────────────────────────────

def test_local_drought_consumes_only_pasture_haystack(session, game_factory, hazard_board, monkeypatch):
    g = game_factory(sheep_per_paddock=3, paddock_type="natural", current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 19
    hu.haystack_pasture = True
    hu.haystack_irrigated = True
    session.commit()

    play_roll(session, g, 1, 2, monkeypatch)  # land on 22 (local drought)

    session.refresh(hu)
    assert hu.is_in_drought
    assert not hu.haystack_pasture      # consumed to offset the drought
    assert hu.haystack_irrigated        # untouched


def test_bore_dries_up_consumes_only_irrigated_haystack(session, game_factory, hazard_board, monkeypatch):
    g = game_factory(sheep_per_paddock=3, paddock_type="irrigated", current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 2
    hu.haystack_pasture = True
    hu.haystack_irrigated = True
    session.commit()

    play_roll(session, g, 1, 2, monkeypatch)  # land on 5 (bore dries up)

    session.refresh(hu)
    assert not hu.haystack_irrigated    # consumed to offset the bore
    assert hu.haystack_pasture          # untouched


def test_fire_destroys_both_haystacks(session, game_factory):
    g = game_factory(sheep_per_paddock=1)
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.haystack_pasture = True
    jim.haystack_irrigated = True
    session.commit()
    from app.services.card_service import CardService
    cs = CardService(session, g.game_id)
    turn = models.Turn(game_id=g.game_id, turn_number=1,
                       active_game_player_id=jim.game_player_id, dice_roll_1=1, dice_roll_2=1)
    session.add(turn); session.flush()
    result = cs._effect_fire_damage(jim, {"cost": 100}, turn.turn_id)
    assert result["haystack_lost"] is True
    session.refresh(jim)
    assert not jim.haystack_pasture and not jim.haystack_irrigated


# ── Buy / sell endpoints ─────────────────────────────────────────────────

def token_for(session, game, name):
    gp = session.query(models.GamePlayer).get(game.players[name])
    tok = f"hay-{name}"
    session.add(models.GameSession(
        session_token=tok, user_id=gp.user_id, game_id=game.game_id,
        expires_at=datetime.now() + timedelta(days=1)))
    session.commit()
    return {"Authorization": f"Bearer {tok}"}


def test_buy_rejects_useless_type(session, game_factory):
    # All-irrigated player cannot buy a pasture haystack.
    g = game_factory(players=(("Hu", False, None),), paddock_type="irrigated")
    client = TestClient(main.app)
    headers = token_for(session, g, "Hu")
    r = client.post(f"/games/{g.game_id}/station/buy-haystack",
                    json={"haystack_type": "pasture"}, headers=headers)
    assert r.status_code == 400
    r2 = client.post(f"/games/{g.game_id}/station/buy-haystack",
                     json={"haystack_type": "irrigated"}, headers=headers)
    assert r2.status_code == 200
    assert session.query(models.GamePlayer).get(g.players["Hu"]).haystack_irrigated


def test_sell_stranded_pasture_haystack(session, game_factory):
    g = game_factory(players=(("Hu", False, None),), paddock_type="irrigated")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.haystack_pasture = True   # stranded after upgrading everything to irrigated
    session.commit()
    client = TestClient(main.app)
    headers = token_for(session, g, "Hu")
    r = client.post(f"/games/{g.game_id}/station/sell-haystack",
                    json={"haystack_type": "pasture"}, headers=headers)
    assert r.status_code == 200 and r.json()["income"] == 350
    assert not session.query(models.GamePlayer).get(g.players["Hu"]).haystack_pasture


# ── Per-type drought premium (regression) ───────────────────────────────

def test_premium_applies_only_to_the_hazard_in_effect(session, game_factory):
    """Max-in-Local-Drought owns both pasture and irrigated: the pasture
    haystack is premium ($1000), the irrigated one stays $500 (his irrigated
    pasture is not under Bore Dries Up)."""
    g = game_factory(players=(("Max", False, None),), paddock_type="natural")
    max_p = session.query(models.GamePlayer).get(g.players["Max"])
    # One improved + the rest, plus an irrigated paddock; in Local Drought.
    pads = session.query(models.Paddock).filter_by(
        game_id=g.game_id, owner_game_player_id=max_p.game_player_id).all()
    pads[0].paddock_type = "improved"
    pads[1].paddock_type = "irrigated"
    max_p.is_in_drought = True
    max_p.bore_dried_up = False
    session.commit()

    offers = {o["type"]: o for o in StationService(session, g.game_id).useful_haystack_offers(max_p)}
    assert offers["pasture"]["cost"] == 1000 and offers["pasture"]["premium"] is True
    assert offers["irrigated"]["cost"] == 500 and offers["irrigated"]["premium"] is False


def test_premium_flips_under_bore_dries_up(session, game_factory):
    g = game_factory(players=(("Max", False, None),), paddock_type="natural")
    max_p = session.query(models.GamePlayer).get(g.players["Max"])
    pads = session.query(models.Paddock).filter_by(
        game_id=g.game_id, owner_game_player_id=max_p.game_player_id).all()
    pads[0].paddock_type = "irrigated"
    max_p.is_in_drought = False
    max_p.bore_dried_up = True
    session.commit()
    offers = {o["type"]: o for o in StationService(session, g.game_id).useful_haystack_offers(max_p)}
    assert offers["irrigated"]["cost"] == 1000 and offers["irrigated"]["premium"] is True
    assert offers["pasture"]["cost"] == 500 and offers["pasture"]["premium"] is False


def test_buy_charges_per_type_price(session, game_factory):
    g = game_factory(players=(("Max", False, None),), paddock_type="natural")
    max_p = session.query(models.GamePlayer).get(g.players["Max"])
    pads = session.query(models.Paddock).filter_by(
        game_id=g.game_id, owner_game_player_id=max_p.game_player_id).all()
    pads[0].paddock_type = "irrigated"
    max_p.is_in_drought = True
    session.commit()
    from app.services.ledger_service import LedgerService
    before = LedgerService(session, g.game_id).player_balance(max_p.game_player_id)
    client = TestClient(main.app)
    headers = token_for(session, g, "Max")
    r = client.post(f"/games/{g.game_id}/station/buy-haystack",
                    json={"haystack_type": "irrigated"}, headers=headers)
    assert r.status_code == 200 and r.json()["cost"] == 500
    after = LedgerService(session, g.game_id).player_balance(max_p.game_player_id)
    assert before - after == 500


# ── Bore Dries Up board marker ───────────────────────────────────────────

def test_bore_dries_up_sets_circuit_marker(session, game_factory, hazard_board, monkeypatch):
    """Landing on Bore Dries Up pins a circuit marker (source + board index)
    so the board can draw it, like Drought / Lucerne Flea / Grass Fire."""
    g = game_factory(sheep_per_paddock=3, paddock_type="irrigated", current="Hu")
    hu = session.query(models.GamePlayer).get(g.players["Hu"])
    hu.current_board_index = 2
    session.commit()

    play_roll(session, g, 1, 2, monkeypatch)  # land on 5 (bore dries up)

    session.refresh(hu)
    assert hu.restock_blocked_until_circuit
    assert hu.restock_block_source == "bore_dries_up"
    assert hu.restock_block_marker_board_index == BORE_INDEX
