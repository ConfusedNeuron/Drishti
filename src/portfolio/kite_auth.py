"""Zerodha Kite Connect daily-login token helpers.

Kite access tokens expire daily (~6 AM IST), so tokens are cached on disk
keyed by calendar date — a cached token is valid as long as it was saved
on the current local date.
"""
import json
from datetime import datetime
from pathlib import Path

from src.config import DATA_DIR

TOKEN_DIR = DATA_DIR / "cache" / "zerodha"
TOKEN_FILENAME = "access_token.json"


def login_url(api_key: str) -> str:
    from kiteconnect import KiteConnect  # lazy import: keep app importable without the package

    return KiteConnect(api_key=api_key).login_url()


def exchange_token(api_key: str, api_secret: str, request_token: str) -> str:
    from kiteconnect import KiteConnect  # lazy import: keep app importable without the package

    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(request_token, api_secret=api_secret)
    return data["access_token"]


def save_token(access_token: str, cache_dir: Path = TOKEN_DIR) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {"access_token": access_token, "date": datetime.now().strftime("%Y-%m-%d")}
    (cache_dir / TOKEN_FILENAME).write_text(json.dumps(payload))


def load_cached_token(cache_dir: Path = TOKEN_DIR) -> str | None:
    token_file = cache_dir / TOKEN_FILENAME
    try:
        data = json.loads(token_file.read_text())
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    # same-calendar-date check is sufficient: Kite tokens expire daily ~6 AM IST
    if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
        return None

    return data.get("access_token")
