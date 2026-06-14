"""Altman Z-score credit screen (Altman 1968; FRM Wk9). Original manufacturing
model. Zones: Z>2.99 safe, 1.81<=Z<=2.99 grey, Z<1.81 distress."""
from __future__ import annotations


def altman_z(working_capital: float, retained_earnings: float, ebit: float,
             mkt_value_equity: float, total_liabilities: float, sales: float,
             total_assets: float) -> dict:
    if total_assets == 0 or total_liabilities == 0:
        return {"z": float("nan"), "zone": "n/a"}
    x1 = working_capital / total_assets
    x2 = retained_earnings / total_assets
    x3 = ebit / total_assets
    x4 = mkt_value_equity / total_liabilities
    x5 = sales / total_assets
    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    zone = "safe" if z > 2.99 else ("distress" if z < 1.81 else "grey")
    return {"z": float(z), "zone": zone,
            "components": {"x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5}}
