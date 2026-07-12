"""Tests for GET /api/frontier/universe and POST /api/frontier/compute
(Efficient Frontier Studio route layer). Diagnostic only — not investment advice."""
import math
from datetime import timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.config import default_dates
from src.dashboard.app import app
import src.dashboard.routes.portfolio as pmod
import src.dashboard.routes.frontier as frontier
from src.dashboard import route_cache
from src.portfolio.frontier_studio import HORIZONS
from src.portfolio.importer import load_sample
from src.research.universe import load_universe

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state():
    yield
    pmod._current_snapshot = None
    route_cache.clear()


def _load_sample_snapshot():
    pmod._current_snapshot = load_sample("nifty-demo-2026")


# ---------------------------------------------------------------------------
# GET /universe
# ---------------------------------------------------------------------------

def test_universe_200_sorted_with_sector():
    r = client.get("/api/frontier/universe")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 100
    assert len(data["candidates"]) == data["count"]
    syms = [row["symbol"] for row in data["candidates"]]
    assert syms == sorted(syms)
    for row in data["candidates"]:
        assert "symbol" in row and "sector" in row


def test_universe_503_when_manifest_missing(monkeypatch):
    monkeypatch.setattr(frontier, "load_universe", lambda: {})
    frontier._universe_list.cache_clear()
    try:
        r = client.get("/api/frontier/universe")
        assert r.status_code == 503
    finally:
        frontier._universe_list.cache_clear()  # don't leak the monkeypatched empty result


# ---------------------------------------------------------------------------
# POST /compute — happy path
# ---------------------------------------------------------------------------

def test_compute_happy_path_1y():
    _load_sample_snapshot()
    r = client.post("/api/frontier/compute", json={"horizon": "1y"})
    assert r.status_code == 200
    data = r.json()

    for key in ("frontier", "band", "current", "tangency", "minvar", "cml",
                "presets", "selected", "gap", "meta", "disclaimer"):
        assert key in data

    assert len(data["frontier"]["risk"]) == len(data["frontier"]["ret"])
    assert data["meta"]["frequency"] == "D"

    minvar_sharpe = (data["minvar"]["ret"] - data["cml"]["rf"]) / data["minvar"]["vol"]
    assert data["tangency"]["sharpe"] >= minvar_sharpe - 1e-9

    for k in ("vol", "ret", "coverage"):
        assert k in data["current"]

    assert "not investment advice" in data["disclaimer"].lower()
    for word in ("buy", "sell", "recommend", "should"):
        assert word not in data["disclaimer"].lower()

    gap = data["gap"]
    assert abs(sum(row["current"] for row in gap) - 1) < 1e-3
    assert abs(sum(row["target"] for row in gap) - 1) < 1e-3


def test_compute_400_when_no_portfolio():
    r = client.post("/api/frontier/compute", json={"horizon": "1y"})
    assert r.status_code == 400


def test_compute_422_bad_horizon():
    _load_sample_snapshot()
    r = client.post("/api/frontier/compute", json={"horizon": "3y"})
    assert r.status_code == 422
    assert "horizon" in r.json()["detail"].lower() or "1y" in r.json()["detail"]


def test_compute_candidate_merge_robust():
    _load_sample_snapshot()
    manifest = load_universe()
    sample_syms = {h.symbol for h in pmod._current_snapshot.holdings}
    known_candidate = None
    for full in manifest:
        sym = full.replace(" IS Equity", "")
        if sym not in sample_syms:
            known_candidate = sym
            break
    assert known_candidate is not None

    r = client.post("/api/frontier/compute", json={
        "horizon": "1y",
        "candidates": [known_candidate, "NOTATICKER"],
    })
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert "NOTATICKER" in meta["unknown_candidates"]
    # robust to which symbols resolve on this cache — at minimum the bogus one is flagged
    assert isinstance(meta["candidates_added"], list)


def test_compute_point_target_vol():
    _load_sample_snapshot()
    r = client.post("/api/frontier/compute", json={"horizon": "1y", "point": 0.25})
    assert r.status_code == 200
    data = r.json()
    assert data["selected"]["kind"] == "target_vol"
    risk = data["frontier"]["risk"]
    assert min(risk) - 1e-6 <= data["selected"]["vol"] <= max(risk) + 1e-6


def test_compute_bool_point_falls_through_to_tangency():
    _load_sample_snapshot()
    r = client.post("/api/frontier/compute", json={"horizon": "1y", "point": True})
    assert r.status_code == 200
    assert r.json()["selected"]["kind"] == "tangency"


def test_compute_cache_hit_skips_recompute(monkeypatch):
    _load_sample_snapshot()

    counter = {"n": 0}
    real_estimate = frontier.estimate_inputs

    def wrapped(*args, **kwargs):
        counter["n"] += 1
        return real_estimate(*args, **kwargs)

    monkeypatch.setattr(frontier, "estimate_inputs", wrapped)

    body = {"horizon": "1y"}
    r1 = client.post("/api/frontier/compute", json=body)
    r2 = client.post("/api/frontier/compute", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert counter["n"] == 1


# ---------------------------------------------------------------------------
# POST /compute — horizon-derived data window (Fable-gate fix)
# ---------------------------------------------------------------------------

def test_compute_data_window_derived_from_horizon(monkeypatch):
    """10y/20y horizons must fetch a window that extends well past the 5y-capped
    default_dates() start; 1y must stay AT LEAST as wide as that default (the route
    clamps to min(horizon_start, default_start) so a short horizon's narrower
    window never replaces the safe 5y default — see frontier.py for why: a
    narrower fetch would starve build_return_matrix's MIN_HISTORY_DAYS filter).
    Empty-frame fake return makes the route 503 right after build_return_matrix —
    that's expected and asserted; what matters is the captured (start, end)."""
    _load_sample_snapshot()

    captured = []

    def fake_build_return_matrix(snap, start, end):
        captured.append((snap, start, end))
        return pd.DataFrame(), []

    monkeypatch.setattr(frontier, "build_return_matrix", fake_build_return_matrix)

    r20 = client.post("/api/frontier/compute", json={"horizon": "20y"})
    r1 = client.post("/api/frontier/compute", json={"horizon": "1y"})

    assert r20.status_code == 503
    assert r1.status_code == 503
    assert len(captured) == 2

    _, start_20, end_20 = captured[0]
    _, start_1, end_1 = captured[1]

    default_start, default_end = default_dates()

    assert end_20 == default_end
    assert end_1 == default_end

    lookback_20y = HORIZONS["20y"][0]
    assert start_20 == end_20 - timedelta(days=math.ceil(lookback_20y * 1.6))
    assert start_20 < default_start
    # 1y's own horizon-derived start (end - ~404 days) is narrower than the 5y
    # default, so the clamp keeps the default — start must equal it, not exceed it.
    assert start_1 == default_start
