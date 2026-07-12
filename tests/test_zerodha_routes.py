"""Tests for Zerodha auth routes: /zerodha/login, /zerodha/callback, /zerodha/token,
and the amended /import/zerodha optional-param fallback. All Kite Connect calls are
monkeypatched — never hit the network."""
import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import app
import src.config as config_mod
import src.dashboard.routes.portfolio as pmod
from src.portfolio import kite_auth

client = TestClient(app)


class FakeKite:
    def __init__(self, api_key=None):
        self.api_key = api_key

    def login_url(self):
        return "https://kite.zerodha.com/connect/login?api_key=fake"

    def generate_session(self, request_token, api_secret=None):
        return {"access_token": "FAKE_ACCESS_TOKEN"}

    def set_access_token(self, token):
        self._t = token

    def holdings(self):
        return [{"tradingsymbol": "RELIANCE", "exchange": "NSE", "quantity": 10,
                  "average_price": 2000.0, "last_price": 2500.0}]


def _set_keys(monkeypatch, key="k", secret="s"):
    monkeypatch.setattr(config_mod.settings, "zerodha_api_key", key)
    monkeypatch.setattr(config_mod.settings, "zerodha_api_secret", secret)


def _reset_snapshot():
    pmod._current_snapshot = None


# ---------------------------------------------------------------------------
# GET /zerodha/login
# ---------------------------------------------------------------------------

def test_login_400_when_keys_unset(monkeypatch):
    _set_keys(monkeypatch, "", "")
    r = client.get("/api/portfolio/zerodha/login")
    assert r.status_code == 400
    assert "ZERODHA_API_KEY" in r.json()["detail"]


def test_login_200_when_keys_set(monkeypatch):
    _set_keys(monkeypatch)
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    r = client.get("/api/portfolio/zerodha/login")
    assert r.status_code == 200
    data = r.json()
    assert "login_url" in data
    assert data["login_url"].startswith("https://kite.zerodha.com")


# ---------------------------------------------------------------------------
# GET /zerodha/callback
# ---------------------------------------------------------------------------

def test_callback_success_redirects_and_sets_snapshot(monkeypatch, tmp_path):
    _reset_snapshot()
    _set_keys(monkeypatch)
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    monkeypatch.setattr(kite_auth, "TOKEN_DIR", tmp_path)

    r = client.get(
        "/api/portfolio/zerodha/callback?request_token=rt&status=success",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/?zerodha=connected"

    # token file written to the monkeypatched cache dir
    token_file = tmp_path / kite_auth.TOKEN_FILENAME
    assert token_file.exists()

    assert pmod._current_snapshot is not None
    assert pmod._current_snapshot.source == "zerodha"


def test_callback_failure_redirects_with_error_and_no_token_leak(monkeypatch, tmp_path):
    """Token is successfully exchanged (FakeKite returns FAKE_ACCESS_TOKEN) but a later
    step (save_token) fails — the error redirect must not leak the token that was
    already obtained."""
    _reset_snapshot()
    _set_keys(monkeypatch)
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    monkeypatch.setattr(kite_auth, "TOKEN_DIR", tmp_path)

    def _raise(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(kite_auth, "save_token", _raise)

    r = client.get(
        "/api/portfolio/zerodha/callback?request_token=rt&status=success",
        follow_redirects=False,
    )
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/?zerodha=error")
    assert "FAKE_ACCESS_TOKEN" not in location


# ---------------------------------------------------------------------------
# POST /zerodha/token
# ---------------------------------------------------------------------------

def test_token_happy_path(monkeypatch, tmp_path):
    _reset_snapshot()
    _set_keys(monkeypatch)
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    monkeypatch.setattr(kite_auth, "TOKEN_DIR", tmp_path)

    r = client.post("/api/portfolio/zerodha/token", json={"request_token": "rt"})
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "zerodha"
    assert "FAKE_ACCESS_TOKEN" not in r.text


def test_token_502_on_exchange_failure(monkeypatch, tmp_path):
    _reset_snapshot()
    _set_keys(monkeypatch)
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    monkeypatch.setattr(kite_auth, "TOKEN_DIR", tmp_path)
    monkeypatch.setattr(kite_auth, "exchange_token",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    r = client.post("/api/portfolio/zerodha/token", json={"request_token": "rt"})
    assert r.status_code == 502


def test_token_400_when_keys_unset(monkeypatch):
    _set_keys(monkeypatch, "", "")
    r = client.post("/api/portfolio/zerodha/token", json={"request_token": "rt"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /import/zerodha — amended optional-param fallback
# ---------------------------------------------------------------------------

def test_import_zerodha_uses_cached_token_when_no_params(monkeypatch):
    _reset_snapshot()
    _set_keys(monkeypatch)
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    monkeypatch.setattr(kite_auth, "load_cached_token", lambda *a, **k: "CACHED_TOKEN")

    r = client.post("/api/portfolio/import/zerodha")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "zerodha"


def test_import_zerodha_400_when_no_token_available(monkeypatch):
    _reset_snapshot()
    _set_keys(monkeypatch)
    monkeypatch.setattr(config_mod.settings, "zerodha_access_token", "")
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)
    monkeypatch.setattr(kite_auth, "load_cached_token", lambda *a, **k: None)

    r = client.post("/api/portfolio/import/zerodha")
    assert r.status_code == 400
    assert "access token" in r.json()["detail"].lower()


def test_import_zerodha_explicit_params_still_work(monkeypatch):
    """Backward compatibility: passing both params explicitly behaves as before."""
    _reset_snapshot()
    monkeypatch.setattr("kiteconnect.KiteConnect", FakeKite)

    r = client.post(
        "/api/portfolio/import/zerodha",
        params={"api_key": "k", "access_token": "explicit-token"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "zerodha"
