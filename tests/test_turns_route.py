"""POST /turns: authorization, sequencing, and the double-submit guard.
SQLite cannot exercise the FOR UPDATE lock itself; what is tested here is
the recheck semantics — a second submit after the turn advanced is a 403,
never a second move."""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from app import models


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def game(game_factory, spaces):
    return game_factory(players=(("Hu", False, None), ("Bo", False, None)),
                        current="Hu")


def token_for(session, game, name):
    gp = session.query(models.GamePlayer).get(game.players[name])
    token = f"test-token-{name}"
    session.add(models.GameSession(
        session_token=token, user_id=gp.user_id, game_id=game.game_id,
        expires_at=datetime.now() + timedelta(days=1)))
    session.commit()
    return {"Authorization": f"Bearer {token}"}


def test_current_player_can_roll(client, session, game):
    r = client.post(f"/games/{game.game_id}/turns", headers=token_for(session, game, "Hu"))
    assert r.status_code == 200
    body = r.json()
    assert body["player_id"] == game.players["Hu"]
    assert 2 <= body["total_roll"] <= 12


def test_double_submit_is_rejected_after_turn_advances(client, session, game):
    headers = token_for(session, game, "Hu")
    assert client.post(f"/games/{game.game_id}/turns", headers=headers).status_code == 200
    r = client.post(f"/games/{game.game_id}/turns", headers=headers)
    assert r.status_code == 403
    assert "not your turn" in r.json()["detail"].lower()
    assert session.query(models.Turn).filter_by(game_id=game.game_id).count() == 1


def test_non_current_player_cannot_roll(client, session, game):
    r = client.post(f"/games/{game.game_id}/turns", headers=token_for(session, game, "Bo"))
    assert r.status_code == 403


def test_cannot_roll_when_game_not_in_progress(client, session, game):
    session.query(models.Game).get(game.game_id).status = "suspended"
    session.commit()
    r = client.post(f"/games/{game.game_id}/turns", headers=token_for(session, game, "Hu"))
    assert r.status_code == 400


def test_cannot_roll_with_unresolved_pending(client, session, game):
    t = models.Turn(game_id=game.game_id, turn_number=1,
                    active_game_player_id=game.players["Hu"],
                    dice_roll_1=1, dice_roll_2=2)
    session.add(t)
    session.flush()
    session.add(models.PendingAction(
        game_id=game.game_id, turn_id=t.turn_id, action_type="expense_payment",
        active_player_id=game.players["Hu"], action_data=json.dumps({})))
    session.commit()
    r = client.post(f"/games/{game.game_id}/turns", headers=token_for(session, game, "Hu"))
    assert r.status_code == 400
    assert "pending" in r.json()["detail"].lower()
