"""MCP tools must work on caller-supplied holdings (Kite-MCP interop) and fall back to sample."""
import pytest
from src.portfolio.importer import snapshot_from_rows

ROWS = [
    {"symbol": "RELIANCE", "quantity": 10, "average_price": 2400, "last_price": 2900},
    {"symbol": "TCS", "quantity": 5, "average_price": 3300, "last_price": 4100},
]


def test_snapshot_from_rows_builds_weighted_snapshot():
    snap = snapshot_from_rows(ROWS)
    assert snap.source == "mcp"
    assert len(snap.holdings) == 2
    assert abs(sum(h.weight for h in snap.holdings) - 1.0) < 1e-9
    assert snap.holdings[0].bbg_ticker.endswith("Equity")


def test_snapshot_from_rows_rejects_empty():
    with pytest.raises(ValueError):
        snapshot_from_rows([])


def test_calculate_portfolio_risk_accepts_holdings():
    from risk_mcp.tools import calculate_portfolio_risk
    out = calculate_portfolio_risk(holdings=ROWS)
    assert isinstance(out, dict)
    assert "disclaimer" in out
    assert out.get("portfolio_id") == "mcp-adhoc" or "var" in str(out).lower()


def test_tools_fall_back_to_sample_without_dashboard(monkeypatch):
    import src.dashboard.routes.portfolio as proutes
    monkeypatch.setattr(proutes, "_current_snapshot", None)
    from risk_mcp.tools import calculate_portfolio_risk
    out = calculate_portfolio_risk()
    assert isinstance(out, dict) and "disclaimer" in out
