"""Lobby identity and rejoin security: a display name is never a credential.
Regression suite for the name-based account takeover fixed in 9db99c6."""
import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    # Plain instantiation: does NOT run startup events (no autopilot task).
    return TestClient(main.app)


@pytest.fixture
def hosted(client):
    r = client.post("/games/create", json={"host_user_name": "Max", "max_players": 6})
    assert r.status_code == 200
    return r.json()


def test_create_issues_session_and_rejoin_code(hosted):
    assert hosted["session_token"]
    assert len(hosted["rejoin_code"]) == 6


def test_fresh_join_issues_rejoin_code(client, hosted):
    r = client.post(f"/games/join/{hosted['game_code']}", json={"player_name": "Bob"})
    assert r.status_code == 200
    assert len(r.json()["rejoin_code"]) == 6


def test_name_alone_cannot_rejoin(client, hosted):
    client.post(f"/games/join/{hosted['game_code']}", json={"player_name": "Bob"})
    r = client.post(f"/games/join/{hosted['game_code']}", json={"player_name": "Bob"})
    assert r.status_code == 403
    assert "rejoin code" in r.json()["detail"].lower()


def test_wrong_rejoin_code_rejected(client, hosted):
    first = client.post(f"/games/join/{hosted['game_code']}",
                        json={"player_name": "Bob"}).json()
    wrong = "000000" if first["rejoin_code"] != "000000" else "111111"
    r = client.post(f"/games/join/{hosted['game_code']}",
                    json={"player_name": "Bob", "rejoin_code": wrong})
    assert r.status_code == 403


def test_correct_code_rejoins_as_same_user_case_insensitive(client, hosted):
    first = client.post(f"/games/join/{hosted['game_code']}",
                        json={"player_name": "Bob"}).json()
    r = client.post(f"/games/join/{hosted['game_code']}",
                    json={"player_name": "bob", "rejoin_code": first["rejoin_code"]})
    assert r.status_code == 200
    assert r.json()["user_id"] == first["user_id"]


def test_ai_seat_cannot_be_claimed_by_name(client, hosted):
    headers = {"Authorization": f"Bearer {hosted['session_token']}"}
    r = client.post(f"/games/{hosted['game_id']}/lobby/add-ai",
                    json={"player_name": "Robo", "difficulty": "easy"}, headers=headers)
    assert r.status_code == 200
    r = client.post(f"/games/join/{hosted['game_code']}",
                    json={"player_name": "Robo", "rejoin_code": "123456"})
    assert r.status_code == 403


def test_lobby_exposes_only_own_rejoin_code(client, hosted):
    client.post(f"/games/join/{hosted['game_code']}", json={"player_name": "Bob"})
    headers = {"Authorization": f"Bearer {hosted['session_token']}"}
    r = client.get(f"/games/{hosted['game_id']}/lobby", headers=headers)
    data = r.json()
    assert data["your_rejoin_code"] == hosted["rejoin_code"]
    assert not any("rejoin" in key for p in data["players"] for key in p)


def test_same_name_in_two_games_is_two_identities(client):
    a = client.post("/games/create", json={"host_user_name": "Alice"}).json()
    b = client.post("/games/create", json={"host_user_name": "Alice"}).json()
    assert a["host_user_id"] != b["host_user_id"]


def test_colliding_normalized_names_both_join(client, hosted):
    """Old bug: synthesized emails collided ('Bob Smith' vs 'bob_smith')
    and the second join 500'd."""
    r1 = client.post(f"/games/join/{hosted['game_code']}", json={"player_name": "Bob Smith"})
    r2 = client.post(f"/games/join/{hosted['game_code']}", json={"player_name": "bob_smith"})
    assert (r1.status_code, r2.status_code) == (200, 200)


def test_session_token_validates(client, hosted):
    r = client.get("/games/session/validate",
                   headers={"Authorization": f"Bearer {hosted['session_token']}"})
    assert r.status_code == 200
    assert r.json()["is_host"] is True


def test_garbage_token_rejected(client, hosted):
    r = client.get(f"/games/{hosted['game_id']}/lobby",
                   headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401
