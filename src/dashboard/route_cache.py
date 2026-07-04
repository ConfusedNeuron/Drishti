"""In-process TTL cache for expensive research endpoints.

Keys include the snapshot's (portfolio_id, as_of); as_of is reset on every
import, so a new portfolio never sees stale entries — TTL only bounds memory
and long-running-server drift.
"""
from __future__ import annotations
import time

_cache: dict[tuple, tuple[float, object]] = {}


def get(key: tuple, max_age_s: float = 3600.0):
    hit = _cache.get(key)
    if hit is None:
        return None
    ts, value = hit
    if time.time() - ts > max_age_s:
        _cache.pop(key, None)
        return None
    return value


def put(key: tuple, value) -> None:
    _cache[key] = (time.time(), value)


def clear() -> None:
    _cache.clear()
