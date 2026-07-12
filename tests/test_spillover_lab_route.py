"""Tests for GET /api/research/spillover/catalog and POST /api/research/spillover/custom
(Spillover Lab route layer). Diagnostic only — not investment advice."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import app
from src.dashboard import route_cache
import src.dashboard.routes.research as research
from src.research import spillover_lab
from src.research.spillover_lab import resolve_series
from src.research.diebold_yilmaz import compute_spillover

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    yield
    route_cache.clear()
    research._spillover_catalog.cache_clear()


EMPTY_CATALOG = {"equities": [], "indices": [], "commodities": [], "macro": [], "sector_composites": []}

SEVEN_SERIES = [
    "idx:NIFTY Index", "idx:NSEBANK Index", "idx:NSEIT Index",
    "idx:NSEFMCG Index", "idx:NSEMET Index", "cmd:CO1 Comdty", "cmd:GC1 Comdty",
]


# ---------------------------------------------------------------------------
# GET /spillover/catalog
# ---------------------------------------------------------------------------

def test_catalog_200_shape_on_real_cache():
    r = client.get("/api/research/spillover/catalog")
    assert r.status_code == 200
    cat = r.json()

    non_empty = [k for k in cat if cat.get(k)]
    assert len(non_empty) >= 4

    assert len(cat["equities"]) == pytest.approx(433, abs=20)
    assert len(cat["sector_composites"]) == pytest.approx(22, abs=5)

    prefixes = {"equities": "eq:", "indices": "idx:", "commodities": "cmd:",
                "macro": "mac:", "sector_composites": "sec:"}
    for cat_name, prefix in prefixes.items():
        for row in cat[cat_name]:
            assert row["id"].startswith(prefix)
            assert "label" in row


def test_catalog_503_when_every_category_empty(monkeypatch):
    monkeypatch.setattr(spillover_lab, "build_catalog", lambda: dict(EMPTY_CATALOG))
    research._spillover_catalog.cache_clear()
    try:
        r = client.get("/api/research/spillover/catalog")
        assert r.status_code == 503
    finally:
        research._spillover_catalog.cache_clear()  # don't leak the monkeypatched empty result


# ---------------------------------------------------------------------------
# POST /spillover/custom — happy path + parity
# ---------------------------------------------------------------------------

def test_custom_happy_path_parity_with_direct_compute():
    body = {"series": SEVEN_SERIES, "fevd_horizon": 10}
    r = client.post("/api/research/spillover/custom", json=body)
    assert r.status_code == 200
    data = r.json()

    for key in ("total_connectedness", "to_spillover", "from_spillover", "net_spillover",
                "pairwise", "var_lag", "fevd_horizon", "rolling", "meta"):
        assert key in data

    assert data["meta"]["n_series"] == 7

    panel = resolve_series(SEVEN_SERIES, None, None)
    tbl = compute_spillover(panel, fevd_horizon=10)

    assert abs(data["total_connectedness"] - tbl.total_spillover) < 1e-9


# ---------------------------------------------------------------------------
# POST /spillover/custom — 422 per cap
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"series": SEVEN_SERIES[:2]},                                        # too few (min 3)
    {"series": [f"idx:X{i} Index" for i in range(13)]},                  # too many (max 12)
    {"series": SEVEN_SERIES, "fevd_horizon": 99},                        # horizon out of range
    {"series": SEVEN_SERIES, "rolling": True, "window": 10, "step": 21}, # window out of range
    {"series": SEVEN_SERIES, "rolling": True, "window": 200, "step": 1}, # step out of range
    {"series": SEVEN_SERIES, "start": "2026-06-01", "end": "2026-06-20"},  # too few aligned obs
])
def test_custom_422_per_cap(body):
    r = client.post("/api/research/spillover/custom", json=body)
    assert r.status_code == 422
    assert r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /spillover/custom — rolling path
# ---------------------------------------------------------------------------

def test_custom_rolling_path_returns_dates_and_values():
    body = {"series": SEVEN_SERIES, "fevd_horizon": 10, "rolling": True, "window": 200, "step": 21}
    r = client.post("/api/research/spillover/custom", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["rolling"] is not None
    assert len(data["rolling"]["dates"]) == len(data["rolling"]["values"])
    assert len(data["rolling"]["dates"]) > 0


# ---------------------------------------------------------------------------
# POST /spillover/custom — cache hit
# ---------------------------------------------------------------------------

def test_custom_cache_hit_skips_recompute(monkeypatch):
    counter = {"n": 0}
    real = research.run_custom_spillover

    def wrapped(*args, **kwargs):
        counter["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(research, "run_custom_spillover", wrapped)

    body = {"series": SEVEN_SERIES, "fevd_horizon": 10}
    r1 = client.post("/api/research/spillover/custom", json=body)
    r2 = client.post("/api/research/spillover/custom", json=body)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert counter["n"] == 1
