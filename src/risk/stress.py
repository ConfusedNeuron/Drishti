"""Stress scenario engine."""
from __future__ import annotations
from src.config import STRESS_SCENARIOS
from src.models import PortfolioSnapshot, StressResult

# Stress override keys (index-style) → canonical GICS sector names on holdings.
_OVERRIDE_KEY_TO_GICS = {
    "energy": "Energy",
    "metals": "Materials",
    "banks": "Financials",
    "fmcg": "Consumer Staples",
    "it": "Information Technology",
    "pharma": "Health Care",
    "auto": "Consumer Discretionary",
}


def run_stress_scenario(
    snapshot: PortfolioSnapshot,
    scenario_id: str,
) -> StressResult:
    if scenario_id not in STRESS_SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_id}'. Available: {list(STRESS_SCENARIOS)}")

    sc = STRESS_SCENARIOS[scenario_id]
    equity_shock = sc.get("equity_shock", 0.0)
    sector_overrides: dict = sc.get("sector_overrides", {})

    contributors = []
    total_loss = 0.0
    affected_sectors = set()

    for h in snapshot.modeled_holdings:
        holding_gics = h.gics_sector if h.gics_sector != "Unknown" else h.sector

        # Find applicable shock — map each override key to its canonical GICS name
        # and match the holding's GICS sector exactly (case-insensitive).
        shock = equity_shock
        for sc_sector, sc_shock in sector_overrides.items():
            canonical = _OVERRIDE_KEY_TO_GICS.get(sc_sector, sc_sector)
            if holding_gics.lower() == canonical.lower():
                shock = sc_shock
                affected_sectors.add(h.sector)
                break

        loss = h.market_value * shock  # negative = loss
        total_loss += loss
        contributors.append({
            "symbol": h.symbol,
            "sector": h.sector,
            "market_value": h.market_value,
            "shock": shock,
            "loss": loss,
        })

    contributors.sort(key=lambda x: x["loss"])  # worst losses first

    return StressResult(
        scenario=scenario_id,
        description=sc.get("description", scenario_id),
        portfolio_loss=total_loss,
        loss_percent=total_loss / snapshot.total_value if snapshot.total_value else 0.0,
        top_contributors=contributors[:5],
        affected_sectors=sorted(affected_sectors),
    )


def run_all_scenarios(snapshot: PortfolioSnapshot) -> list[StressResult]:
    return [run_stress_scenario(snapshot, sid) for sid in STRESS_SCENARIOS]
