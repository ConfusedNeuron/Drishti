"""Spillover Lab tab skeleton — panel/id presence, script-order presence checks,
and a contract pin on POST /api/research/spillover/custom against the renderer.

Mirrors tests/test_frontier_tab.py. The Plotly render itself cannot be exercised
headlessly here; this pins the served-HTML wiring and the payload shape
consumed by spillover.js:renderLabResults."""
from fastapi.testclient import TestClient

from src.dashboard.app import app

client = TestClient(app)


def test_index_page_loads():
    r = client.get("/")
    assert r.status_code == 200


def test_spillover_lab_section_present():
    r = client.get("/")
    assert 'id="spillover-lab"' in r.text


def test_spillover_lab_controls_present():
    r = client.get("/")
    text = r.text
    for el_id in (
        "lab-category", "lab-series-dl", "lab-series-input", "lab-run",
        "lab-error", "lab-net-chart", "lab-heatmap", "lab-rolling-chart",
        "lab-total", "lab-meta", "lab-chips", "lab-count",
        "lab-start", "lab-end", "lab-horizon", "lab-rolling", "lab-window", "lab-step",
    ):
        assert f'id="{el_id}"' in text, f"missing #{el_id}"


def test_spillover_lab_run_button_disabled_by_default():
    r = client.get("/")
    assert 'id="lab-run" onclick="runSpilloverLab()" disabled' in r.text


def test_spillover_script_tag_present():
    r = client.get("/")
    assert "/static/js/spillover.js" in r.text


def test_spillover_script_load_order_unchanged():
    r = client.get("/")
    text = r.text
    idx_research = text.index("research.js")
    idx_spillover = text.index("spillover.js")
    idx_events = text.index("events.js")
    assert idx_research < idx_spillover < idx_events


def test_custom_payload_matches_lab_renderer_contract():
    """Pins the JS<->payload contract consumed by spillover.js:renderLabResults.
    Backend (Tasks 1-2) already implements this — not RED/GREEN on behavior,
    a contract pin against regressions in the payload shape the frontend
    renderer depends on."""
    body = {
        "series": [
            "idx:NIFTY Index", "idx:NSEBANK Index", "idx:NSEIT Index",
            "idx:NSEFMCG Index", "idx:NSEMET Index",
        ],
        "fevd_horizon": 10,
    }
    r = client.post("/api/research/spillover/custom", json=body)
    assert r.status_code == 200
    d = r.json()

    assert isinstance(d["total_connectedness"], float)
    assert isinstance(d["net_spillover"], dict) and d["net_spillover"]
    assert isinstance(d["pairwise"], dict) and d["pairwise"]
    # pairwise is dict-of-dicts (row -> {col -> value}) — the heatmap renderer
    # indexes into the first row's keys to build the column axis.
    first_row = next(iter(d["pairwise"].values()))
    assert isinstance(first_row, dict) and first_row

    assert isinstance(d["var_lag"], int)
    assert d["meta"]["n_obs"] > 0
    assert d["meta"]["start"] and d["meta"]["end"]
    assert d["meta"]["n_series"] == 5
    assert "rolling" in d  # None or {"dates": [...], "values": [...]}
