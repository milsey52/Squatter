"""Session lifecycle: expiry is enforced (in UTC) and expired rows are
swept opportunistically whenever a new token is minted."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import main
from app import models
from app.utils.time import utc_now


@pytest.fixture
def client():
    return TestClient(main.app)


def make_session(session, game, name, *, expired=False):
    gp = session.query(models.GamePlayer).get(game.players[name])
    token = f"tok-{name}-{'old' if expired else 'new'}"
    delta = timedelta(days=-1) if expired else timedelta(days=1)
    session.add(models.GameSession(
        session_token=token, user_id=gp.user_id, game_id=game.game_id,
        expires_at=utc_now() + delta))
    session.commit()
    return token


def test_expired_token_is_rejected(client, session, game_factory):
    g = game_factory()
    token = make_session(session, g, "Hu", expired=True)
    r = client.get(f"/games/{g.game_id}/lobby",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


def test_expired_token_rejected_on_sse_endpoint(client, session, game_factory):
    g = game_factory()
    token = make_session(session, g, "Hu", expired=True)
    r = client.get(f"/games/{g.game_id}/events?token={token}")
    assert r.status_code == 401


def test_valid_token_accepted(client, session, game_factory):
    g = game_factory()
    token = make_session(session, g, "Hu")
    r = client.get(f"/games/{g.game_id}/lobby",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_expired_sessions_swept_on_new_token_mint(client, session, game_factory):
    g = game_factory()
    make_session(session, g, "Hu", expired=True)
    make_session(session, g, "Hu")  # valid one must survive the sweep
    assert session.query(models.GameSession).count() == 2

    # Creating a game mints a token -> sweeps expired rows.
    r = client.post("/games/create", json={"host_user_name": "Sweeper"})
    assert r.status_code == 200

    session.expire_all()
    remaining = session.query(models.GameSession).all()
    tokens = {s.session_token for s in remaining}
    assert "tok-Hu-old" not in tokens   # expired: swept
    assert "tok-Hu-new" in tokens       # valid: kept
    assert len(remaining) == 2          # valid + the newly minted one
