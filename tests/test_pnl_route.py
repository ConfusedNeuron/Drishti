"""Tests for GET /api/portfolio/pnl — per-holding unrealized P&L."""
import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import app
import src.dashboard.routes.portfolio as pmod
from src.portfolio.importer import load_sample
from src.models import Holding, PortfolioSnapshot

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_snapshot():
    """Ensure no test leaks its snapshot into the next one."""
    yield
    pmod._current_snapshot = None


def test_pnl_route_returns_400_when_no_portfolio_loaded():
    pmod._current_snapshot = None
    r = client.get("/api/portfolio/pnl")
    assert r.status_code == 400


def test_pnl_route_on_sample_portfolio():
    snap = load_sample("nifty-demo-2026")
    pmod._current_snapshot = snap

    r = client.get("/api/portfolio/pnl")
    assert r.status_code == 200
    data = r.json()

    rows = data["rows"]
    assert len(rows) == len(snap.holdings)

    # sorted by market_value descending (non-increasing)
    mvs = [row["market_value"] for row in rows]
    assert mvs == sorted(mvs, reverse=True)

    # pick a row with invested > 0 and check the arithmetic
    row = next(r_ for r_ in rows if r_["quantity"] * r_["average_price"] != 0)
    invested = row["quantity"] * row["average_price"]
    assert row["invested"] == pytest.approx(invested)
    assert row["pnl"] == pytest.approx(row["market_value"] - invested)
    assert row["pnl_pct"] == pytest.approx(row["pnl"] / invested)

    totals = data["totals"]
    assert totals["market_value"] == pytest.approx(sum(r_["market_value"] for r_ in rows))
    assert totals["invested"] == pytest.approx(sum(r_["invested"] for r_ in rows))
    assert totals["pnl"] == pytest.approx(totals["market_value"] - totals["invested"])
    if totals["invested"] != 0:
        assert totals["pnl_pct"] == pytest.approx(totals["pnl"] / totals["invested"])

    assert data["source"] == snap.source
    assert data["as_of"] == snap.as_of


def test_pnl_route_guards_divide_by_zero():
    zero_holding = Holding(
        symbol="ZEROAVG",
        exchange="NSE",
        bbg_ticker="ZEROAVG IN Equity",
        quantity=10,
        average_price=0.0,
        last_price=100.0,
        market_value=1000.0,
        weight=1.0,
        sector="Unknown",
    )
    snap = PortfolioSnapshot(
        portfolio_id="zero-avg-test",
        holdings=[zero_holding],
        total_value=1000.0,
        modeled_value=1000.0,
        source="test",
        as_of="2026-07-06T00:00:00",
    )
    pmod._current_snapshot = snap

    r = client.get("/api/portfolio/pnl")
    assert r.status_code == 200
    data = r.json()
    assert len(data["rows"]) == 1
    assert data["rows"][0]["pnl_pct"] is None
