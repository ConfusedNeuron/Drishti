"""
Tests for src/risk/stress.py — sector override GICS mapping.

Verifies that sector_overrides keyed by index-style names (banks, it, energy, …)
correctly map to canonical GICS sector names on Holding objects and that overrides
fire instead of falling back to the generic equity_shock.
"""
from __future__ import annotations

import pytest

from src.config import STRESS_SCENARIOS
from src.models import Holding, PortfolioSnapshot
from src.risk.stress import run_stress_scenario


def _make_holding(symbol: str, gics_sector: str, market_value: float = 100_000.0) -> Holding:
    return Holding(
        symbol=symbol,
        exchange="NSE",
        bbg_ticker=f"{symbol} IN Equity",
        quantity=100,
        average_price=market_value / 100,
        last_price=market_value / 100,
        market_value=market_value,
        weight=0.0,
        sector=gics_sector,      # display sector (same value, simplest setup)
        gics_sector=gics_sector,
        asset_type="EQUITY",
        modeled=True,
    )


def _make_snapshot(holdings: list[Holding]) -> PortfolioSnapshot:
    total = sum(h.market_value for h in holdings)
    for h in holdings:
        h.weight = h.market_value / total
    return PortfolioSnapshot(
        portfolio_id="test",
        holdings=holdings,
        total_value=total,
        modeled_value=total,
        source="test",
    )


# ── FIX 1: banks override fires for Financials holdings ───────────────────

def test_financials_holding_gets_banks_override_covid():
    """
    covid_march2020 has sector_overrides["banks"] = -0.42.
    A holding with gics_sector="Financials" must receive shock=-0.42,
    NOT the generic equity_shock (-0.35).
    """
    sc = STRESS_SCENARIOS["covid_march2020"]
    banks_shock = sc["sector_overrides"]["banks"]   # -0.42
    equity_shock = sc["equity_shock"]               # -0.35

    fin_holding = _make_holding("HDFCB", "Financials")
    snap = _make_snapshot([fin_holding])

    result = run_stress_scenario(snap, "covid_march2020")

    assert len(result.top_contributors) == 1
    contrib = result.top_contributors[0]
    assert contrib["symbol"] == "HDFCB"
    assert abs(contrib["shock"] - banks_shock) < 1e-9, (
        f"Expected banks override shock {banks_shock}, got {contrib['shock']}. "
        "Financials→banks mapping likely broken."
    )
    assert abs(contrib["shock"] - equity_shock) > 1e-9, (
        "Financials holding incorrectly received generic equity_shock — override did not fire."
    )


# ── FIX 1: it override fires for Information Technology holdings ───────────

def test_it_holding_gets_it_override_rate_hike():
    """
    rate_hike_100bps has sector_overrides["it"] = -0.03.
    A holding with gics_sector="Information Technology" must receive shock=-0.03,
    NOT the generic equity_shock (-0.05).
    """
    sc = STRESS_SCENARIOS["rate_hike_100bps"]
    it_shock = sc["sector_overrides"]["it"]         # -0.03
    equity_shock = sc["equity_shock"]               # -0.05

    it_holding = _make_holding("INFY", "Information Technology")
    snap = _make_snapshot([it_holding])

    result = run_stress_scenario(snap, "rate_hike_100bps")

    contrib = result.top_contributors[0]
    assert contrib["symbol"] == "INFY"
    assert abs(contrib["shock"] - it_shock) < 1e-9, (
        f"Expected it override shock {it_shock}, got {contrib['shock']}. "
        "Information Technology→it mapping likely broken."
    )
    assert abs(contrib["shock"] - equity_shock) > 1e-9, (
        "IT holding incorrectly received generic equity_shock — override did not fire."
    )


# ── FIX 1: all override keys resolve correctly ────────────────────────────

@pytest.mark.parametrize("override_key,gics_sector,scenario_id", [
    ("energy",  "Energy",                   "covid_march2020"),
    ("metals",  "Materials",                "covid_march2020"),
    ("banks",   "Financials",               "covid_march2020"),
    ("fmcg",    "Consumer Staples",         "crude_shock_2022"),
    ("it",      "Information Technology",   "rate_hike_100bps"),
    ("pharma",  "Health Care",              "inr_depreciation_10pct"),
    # "auto" (Consumer Discretionary) has no override in any current scenario;
    # tested separately in test_auto_sector_falls_back_to_equity_shock.
])
def test_all_override_keys_fire(override_key, gics_sector, scenario_id):
    """Each override key must produce the scenario's defined shock on the matching GICS sector."""
    sc = STRESS_SCENARIOS[scenario_id]
    expected_shock = sc["sector_overrides"][override_key]
    equity_shock = sc.get("equity_shock", 0.0)

    holding = _make_holding("TEST", gics_sector)
    snap = _make_snapshot([holding])
    result = run_stress_scenario(snap, scenario_id)

    contrib = result.top_contributors[0]
    assert abs(contrib["shock"] - expected_shock) < 1e-9, (
        f"override_key={override_key!r} gics={gics_sector!r} scenario={scenario_id}: "
        f"expected shock={expected_shock}, got {contrib['shock']}"
    )


def test_auto_sector_falls_back_to_equity_shock():
    """
    'auto' (Consumer Discretionary) is in _OVERRIDE_KEY_TO_GICS but has no override
    in any current STRESS_SCENARIOS. A Consumer Discretionary holding must receive
    the generic equity_shock in a scenario with no auto override.
    """
    sc = STRESS_SCENARIOS["covid_march2020"]
    equity_shock = sc["equity_shock"]  # -0.35

    holding = _make_holding("TATAMOTORS", "Consumer Discretionary")
    snap = _make_snapshot([holding])
    result = run_stress_scenario(snap, "covid_march2020")

    contrib = result.top_contributors[0]
    assert abs(contrib["shock"] - equity_shock) < 1e-9, (
        f"Consumer Discretionary: expected equity_shock fallback {equity_shock}, got {contrib['shock']}"
    )


# ── FIX 1: unmatched sector falls back to equity_shock ────────────────────

def test_unknown_sector_falls_back_to_equity_shock():
    """A holding with a GICS sector not in any override must receive the generic equity_shock."""
    sc = STRESS_SCENARIOS["covid_march2020"]
    equity_shock = sc["equity_shock"]  # -0.35

    holding = _make_holding("NIFTY", "Real Estate")
    snap = _make_snapshot([holding])
    result = run_stress_scenario(snap, "covid_march2020")

    contrib = result.top_contributors[0]
    assert abs(contrib["shock"] - equity_shock) < 1e-9, (
        f"Expected equity_shock fallback {equity_shock}, got {contrib['shock']}"
    )


# ── FIX 1: mixed portfolio — each holding gets its own shock ──────────────

def test_mixed_portfolio_each_sector_gets_correct_shock():
    """
    Portfolio with Financials + IT + Energy + Real Estate (unknown).
    covid_march2020: banks=-0.42, energy=-0.45, metals=-0.40; equity_shock=-0.35.
    IT has no override in covid → equity_shock. Real Estate → equity_shock.
    """
    sc = STRESS_SCENARIOS["covid_march2020"]
    sector_shocks = {
        "Financials":            sc["sector_overrides"]["banks"],   # -0.42
        "Information Technology": sc["equity_shock"],               # no IT override in covid
        "Energy":                sc["sector_overrides"]["energy"],   # -0.45
        "Real Estate":           sc["equity_shock"],                # no override
    }

    holdings = [_make_holding(sym, sec) for sym, sec in [
        ("HDFCB", "Financials"),
        ("INFY",  "Information Technology"),
        ("ONGC",  "Energy"),
        ("DLFU",  "Real Estate"),
    ]]
    snap = _make_snapshot(holdings)
    result = run_stress_scenario(snap, "covid_march2020")

    contrib_map = {c["symbol"]: c["shock"] for c in result.top_contributors}
    # top_contributors is sorted worst-first (may be < 4 if some tie), iterate all
    # Rebuild from the full result — top_contributors is top-5, all 4 symbols should appear
    for sym, sec in [("HDFCB", "Financials"), ("INFY", "Information Technology"),
                     ("ONGC", "Energy"), ("DLFU", "Real Estate")]:
        assert sym in contrib_map, f"{sym} not in top_contributors"
        assert abs(contrib_map[sym] - sector_shocks[sec]) < 1e-9, (
            f"{sym} ({sec}): expected {sector_shocks[sec]}, got {contrib_map[sym]}"
        )
