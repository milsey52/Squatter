"""The player holdings endpoint includes a financial statement (cash, sheep,
paddocks/mortgages, rams, haystack, liquidation value, net worth) — usable
as a post-mortem for a bankrupt station, whose assets stay frozen."""
import pytest
from fastapi.testclient import TestClient

import main
from app import models
from tests.conftest import drain_cash


@pytest.fixture
def client():
    return TestClient(main.app)


def test_holdings_reports_financials(client, session, game_factory):
    g = game_factory(sheep_per_paddock=2)  # 10 natural pens, 5 paddocks
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.has_haystack = True
    session.commit()

    r = client.get(f"/games/{g.game_id}/players/{g.players['Jim']}/holdings")
    assert r.status_code == 200
    fin = r.json()["financials"]
    assert fin["cash"] == 2000
    assert fin["sheep_pens"] == 10
    assert fin["sheep_count"] == 10 * 200
    assert fin["paddocks_owned"] == 5
    assert fin["paddocks_mortgaged"] == 0
    assert fin["has_haystack"] is True
    # 10 pens x $400 + 5 natural mortgages x $100 + $350 haystack = 4850
    assert fin["liquidation_value"] == 4000 + 500 + 350
    assert fin["net_worth"] == 2000 + 4850


def test_holdings_shows_bankrupt_state_and_negative_net_worth(client, session, game_factory):
    g = game_factory(players=(("Hu", False, None), ("Jim", True, "medium")),
                     sheep_per_paddock=0, current="Jim")
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    # Mortgage everything and drive cash deep negative so net worth < 0.
    for p in session.query(models.Paddock).filter_by(
            game_id=g.game_id, owner_game_player_id=jim.game_player_id):
        p.is_mortgaged = True
    jim.is_active = False
    session.commit()
    drain_cash(session, g.game_id, jim.game_player_id, 2600)  # balance -600

    r = client.get(f"/games/{g.game_id}/players/{g.players['Jim']}/holdings")
    body = r.json()
    assert body["is_active"] is False
    fin = body["financials"]
    assert fin["cash"] == -600
    assert fin["paddocks_mortgaged"] == 5
    assert fin["liquidation_value"] == 0   # nothing left to sell
    assert fin["net_worth"] == -600
