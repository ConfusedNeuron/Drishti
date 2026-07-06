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
