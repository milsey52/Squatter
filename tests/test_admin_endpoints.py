"""Admin endpoints: POST-only, disabled without ADMIN_SECRET, constant-time
header check. Regression suite for the unauthenticated-GET wipe fixed in
398adbc. The success path is intentionally untested — it truncates tables."""
import pytest
from fastapi.testclient import TestClient

import main

ENDPOINTS = ["/admin/reset-all-games", "/admin/reseed-static-data"]


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_get_is_rejected(client, endpoint):
    assert client.get(endpoint).status_code == 405


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_disabled_without_configured_secret(client, endpoint, monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    r = client.post(endpoint)
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_missing_header_rejected(client, endpoint, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    assert client.post(endpoint).status_code == 403


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_wrong_secret_rejected(client, endpoint, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "s3cret")
    r = client.post(endpoint, headers={"X-Admin-Secret": "wrong"})
    assert r.status_code == 403
