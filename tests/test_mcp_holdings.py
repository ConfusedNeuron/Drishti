"""MCP tools must work on caller-supplied holdings (Kite-MCP interop) and fall back to sample."""
import pytest
from src.portfolio.importer import snapshot_from_rows

ROWS = [
    {"symbol": "RELIANCE", "quantity": 10, "average_price": 2400, "last_price": 2900},
    {"symbol": "TCS", "quantity": 5, "average_price": 3300, "last_price": 4100},
]

ROWS_VALUE = 10 * 2900 + 5 * 4100  # 49500


def test_snapshot_from_rows_builds_weighted_snapshot():
    snap = snapshot_from_rows(ROWS)
    assert snap.source == "mcp"
    assert len(snap.holdings) == 2
    assert abs(sum(h.weight for h in snap.holdings) - 1.0) < 1e-9
    assert snap.holdings[0].bbg_ticker.endswith("Equity")


def test_snapshot_from_rows_rejects_empty():
    with pytest.raises(ValueError):
        snapshot_from_rows([])


def test_snapshot_from_rows_rejects_missing_key_with_row_index():
    with pytest.raises(ValueError, match="row 0 missing key 'average_price'"):
        snapshot_from_rows([{"symbol": "RELIANCE", "quantity": 10}])


def test_calculate_portfolio_risk_accepts_holdings():
    from risk_mcp.tools import calculate_portfolio_risk
    out = calculate_portfolio_risk(holdings=ROWS)
    assert isinstance(out, dict)
    assert "disclaimer" in out
    assert out["portfolio_source"] == "mcp"
    assert out["portfolio_id"] == "mcp-adhoc"
    assert out["portfolio_value"] == pytest.approx(ROWS_VALUE)


def test_tools_fall_back_to_sample_without_dashboard(monkeypatch):
    import src.dashboard.routes.portfolio as proutes
    monkeypatch.setattr(proutes, "_current_snapshot", None)
    from risk_mcp.tools import calculate_portfolio_risk
    out = calculate_portfolio_risk()
    assert isinstance(out, dict) and "disclaimer" in out
    assert out["portfolio_source"] == "sample"


def test_tools_use_dashboard_snapshot_when_loaded(monkeypatch):
    import src.dashboard.routes.portfolio as proutes
    dash_snap = snapshot_from_rows(ROWS, portfolio_id="dash-live", source="dashboard")
    monkeypatch.setattr(proutes, "_current_snapshot", dash_snap)
    from risk_mcp.tools import calculate_portfolio_risk
    out = calculate_portfolio_risk()
    assert out["portfolio_source"] == "dashboard"
    assert out["portfolio_id"] == "dash-live"


def test_malformed_holdings_return_error_dict_not_exception():
    from risk_mcp.tools import calculate_portfolio_risk
    out = calculate_portfolio_risk(holdings=[{"symbol": "RELIANCE", "quantity": 10}])
    assert isinstance(out, dict)
    assert "error" in out
    assert "average_price" in out["error"]
