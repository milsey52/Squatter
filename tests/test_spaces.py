"""The /games/spaces endpoint serves the static board layout used by the
client to link board spaces to the manual. It must resolve (not be captured
by /games/{game_id}) and return each space's index, name, type and season."""
import pytest
from fastapi.testclient import TestClient

import main
from app import models


@pytest.fixture
def client():
    return TestClient(main.app)


def test_spaces_endpoint_returns_layout(client, session):
    session.add(models.Space(board_index=0, name="Start/Wool Sale", space_type="wool_sale"))
    session.add(models.Space(board_index=1, name="Stock Sale", space_type="stock_sale"))
    session.add(models.Space(board_index=40, name="Jet Sheep", space_type="expense", season="Haymaking"))
    session.commit()

    r = client.get("/games/spaces")
    assert r.status_code == 200
    spaces = r.json()["spaces"]
    by_index = {s["board_index"]: s for s in spaces}
    assert by_index[0]["space_type"] == "wool_sale"
    assert by_index[1]["name"] == "Stock Sale"
    assert by_index[40]["season"] == "Haymaking"
