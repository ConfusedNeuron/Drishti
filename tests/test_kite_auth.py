import json
from datetime import datetime

import pytest

from src.portfolio import kite_auth


def test_save_then_load_round_trips_token(tmp_path):
    kite_auth.save_token("secret-token-123", cache_dir=tmp_path)
    loaded = kite_auth.load_cached_token(tmp_path)
    assert loaded == "secret-token-123"


def test_stale_date_returns_none(tmp_path):
    token_file = tmp_path / "access_token.json"
    token_file.write_text(json.dumps({"access_token": "old-token", "date": "2000-01-01"}))
    assert kite_auth.load_cached_token(tmp_path) is None


def test_missing_file_returns_none(tmp_path):
    assert kite_auth.load_cached_token(tmp_path) is None


def test_valid_non_dict_json_returns_none(tmp_path):
    token_file = tmp_path / "access_token.json"
    token_file.write_text("123")
    assert kite_auth.load_cached_token(tmp_path) is None


def test_corrupt_json_returns_none(tmp_path):
    token_file = tmp_path / "access_token.json"
    token_file.write_bytes(b"not valid json {{{")
    assert kite_auth.load_cached_token(tmp_path) is None


def test_save_token_writes_expected_keys(tmp_path):
    kite_auth.save_token("another-token", cache_dir=tmp_path)
    token_file = tmp_path / "access_token.json"
    data = json.loads(token_file.read_text())
    assert data["access_token"] == "another-token"
    assert data["date"] == datetime.now().strftime("%Y-%m-%d")


def test_login_url_uses_kiteconnect(monkeypatch):
    class FakeKiteConnect:
        def __init__(self, api_key):
            self.api_key = api_key

        def login_url(self):
            return f"https://kite.zerodha.com/connect/login?api_key={self.api_key}"

    import kiteconnect

    monkeypatch.setattr(kiteconnect, "KiteConnect", FakeKiteConnect, raising=False)
    url = kite_auth.login_url("my-api-key")
    assert url == "https://kite.zerodha.com/connect/login?api_key=my-api-key"


def test_exchange_token_uses_kiteconnect(monkeypatch):
    class FakeKiteConnect:
        def __init__(self, api_key):
            self.api_key = api_key

        def generate_session(self, request_token, api_secret):
            return {"access_token": "exchanged-token", "request_token": request_token}

    import kiteconnect

    monkeypatch.setattr(kiteconnect, "KiteConnect", FakeKiteConnect, raising=False)
    token = kite_auth.exchange_token("api-key", "api-secret", "req-token")
    assert token == "exchanged-token"
