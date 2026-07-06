"""Frontier tab skeleton — nav button, panel, and script-order presence checks.

The Plotly chart + weight-gap table render is Task 5; this only verifies the
tab wiring (nav button, panel div, script tag, and load order) landed in the
served HTML.
"""
from fastapi.testclient import TestClient

from src.dashboard.app import app

client = TestClient(app)


def test_index_page_loads():
    r = client.get("/")
    assert r.status_code == 200


def test_frontier_panel_present():
    r = client.get("/")
    assert 'id="tab-frontier"' in r.text


def test_frontier_nav_button_present():
    r = client.get("/")
    assert "showTab('frontier'" in r.text


def test_frontier_script_tag_present():
    r = client.get("/")
    assert "/static/js/frontier.js" in r.text


def test_frontier_script_load_order():
    r = client.get("/")
    text = r.text
    idx_regimes = text.index("regimes.js")
    idx_frontier = text.index("frontier.js")
    idx_copilot = text.index("copilot.js")
    assert idx_regimes < idx_frontier < idx_copilot


def test_compute_payload_matches_renderer_contract():
    """Pins the JS<->payload contract consumed by renderFrontierChart/renderFrontierGap
    (Task 5, frontier.js). Backend (Task 1-4) already implements this — this test is
    not RED/GREEN on behavior, it is a contract pin against regressions in the payload
    shape the frontend renderers depend on."""
    client.post("/api/portfolio/import/sample?sample_id=nifty-demo-2026")
    r = client.post("/api/frontier/compute", json={"horizon": "1y"})
    assert r.status_code == 200
    d = r.json()

    assert isinstance(d["frontier"]["risk"], list)
    assert isinstance(d["band"]["risk_lo"], list)
    assert "rf" in d["cml"]
    assert d["presets"][0]["vol"] is not None
    assert d["selected"]["kind"] in ("tangency", "minvar", "target_vol")
    assert isinstance(d["gap"], list)
    assert "coverage" in d["current"]
