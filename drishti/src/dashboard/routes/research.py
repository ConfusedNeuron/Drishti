"""Research routes — DCC-GARCH, Diebold-Yilmaz, HMM regime, IC/Granger."""
from __future__ import annotations
import dataclasses
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from src.dashboard.routes.portfolio import get_snapshot
from src.risk.returns import (
    build_return_matrix, portfolio_returns,
    load_factor_series, load_sector_returns,
)

router = APIRouter()


def _default_dates() -> tuple[date, date]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=365 * 5)
    return start, end


@router.get("/regime")
async def regime_endpoint():
    snap = get_snapshot()
    start, end = _default_dates()
    returns_df, _ = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise HTTPException(status_code=503, detail="No cached price data.")

    port_ret = portfolio_returns(returns_df, snap.weights)

    # VIX if cached
    vix = load_factor_series(["indiavix"], start, end)
    vix_series = vix["indiavix"] if "indiavix" in vix.columns else None

    from src.research.hmm import build_hmm_features, walk_forward_hmm, regime_conditioned_var
    try:
        regime_hist = walk_forward_hmm(port_ret, vix_series)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HMM fitting failed: {e}")

    rcv = regime_conditioned_var(port_ret, regime_hist, snap.total_value)

    # Add regime history for chart
    rcv["regime_history"] = {
        "dates": [str(d.date()) for d in regime_hist.index],
        "regime": regime_hist["regime"].tolist(),
        "prob_high_vol": regime_hist["prob_high_vol"].tolist(),
    }
    return rcv


@router.get("/ic")
async def ic_endpoint(lags: str = "1,2,3,5,10"):
    snap = get_snapshot()
    start, end = _default_dates()
    returns_df, _ = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise HTTPException(status_code=503, detail="No cached price data.")

    factors = load_factor_series(["brent", "gold", "copper", "usdinr", "gsec10y"], start, end)
    sectors = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)

    if factors.empty or sectors.empty:
        raise HTTPException(status_code=503, detail="No factor/sector data cached.")

    from src.research.ic import run_full_ic_study
    lag_list = [int(x) for x in lags.split(",")]
    result = run_full_ic_study(factors, sectors, lags=lag_list)

    return {
        "ic_results": [dataclasses.asdict(r) for r in result["ic_results"]],
        "granger_results": [dataclasses.asdict(r) for r in result["granger_results"]],
        "n_tests": result["n_tests"],
        "note": "IC is time-series rolling correlation (lag factor vs. target). BH FDR correction applied.",
    }


@router.get("/spillover")
async def spillover_endpoint(fevd_horizon: int = 10):
    start, end = _default_dates()
    factors = load_factor_series(["brent", "gold", "copper", "usdinr"], start, end)
    sectors = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)

    if factors.empty or sectors.empty:
        raise HTTPException(status_code=503, detail="No factor/sector data cached.")

    import pandas as pd
    combined = pd.concat([sectors, factors], axis=1).dropna()

    from src.research.diebold_yilmaz import compute_spillover
    try:
        tbl = compute_spillover(combined, fevd_horizon=fevd_horizon)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spillover computation failed: {e}")

    return {
        "total_connectedness": tbl.total_spillover,
        "to_spillover": tbl.to_spillover,
        "from_spillover": tbl.from_spillover,
        "net_spillover": tbl.net_spillover,
        "pairwise": tbl.pairwise.to_dict(),
        "var_lag": tbl.var_lag,
        "fevd_horizon": tbl.fevd_horizon,
    }


@router.get("/dcc")
async def dcc_endpoint():
    start, end = _default_dates()
    factors = load_factor_series(["brent", "gold"], start, end)
    sectors = load_sector_returns(["energy", "metals"], start, end)

    if factors.empty or sectors.empty:
        raise HTTPException(status_code=503, detail="No factor/sector data cached.")

    import pandas as pd
    combined = pd.concat([sectors, factors], axis=1).dropna()

    from src.research.dcc_garch import fit_dcc_garch, crisis_correlation_summary
    try:
        result = fit_dcc_garch(combined)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DCC-GARCH failed: {e}")

    corr_df = result["correlations"]
    crisis = crisis_correlation_summary(corr_df)

    return {
        "dcc_alpha": result["dcc_alpha"],
        "dcc_beta": result["dcc_beta"],
        "time_varying_correlations": {
            col: {
                "dates": [str(d.date()) for d in corr_df.index],
                "values": corr_df[col].tolist(),
            }
            for col in corr_df.columns
        },
        "crisis_summary": crisis.to_dict(),
    }
