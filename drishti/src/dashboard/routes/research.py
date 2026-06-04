"""Research routes — DCC-GARCH, Diebold-Yilmaz, HMM regime, IC/Granger."""
from __future__ import annotations
import dataclasses

from fastapi import APIRouter, HTTPException

from src.config import default_dates as _default_dates
from src.dashboard.routes.portfolio import get_snapshot
from src.risk.returns import (
    build_return_matrix, portfolio_returns,
    load_factor_series, load_sector_returns,
)

router = APIRouter()


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


@router.get("/walkforward")
async def walkforward_endpoint():
    start, end = _default_dates()
    factors = load_factor_series(["brent", "gold", "copper", "usdinr", "gsec10y"], start, end)
    sectors = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)

    if factors.empty or sectors.empty:
        raise HTTPException(status_code=503, detail="No factor/sector data cached.")

    # Try to load pre-computed IC results from BQuant artifact export
    import json
    from src.config import ARTIFACTS_DIR
    ic_results: list[dict] | None = None
    artifact_path = ARTIFACTS_DIR / "factor_ic_results.json"
    if artifact_path.exists():
        try:
            with open(artifact_path) as f:
                ic_data = json.load(f)
            ic_results = ic_data.get("results", [])
        except Exception:
            ic_results = None

    from src.research.walk_forward import run_walk_forward
    import dataclasses
    try:
        result = run_walk_forward(factors, sectors, ic_results=ic_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Walk-forward failed: {e}")

    return {
        "n_pairs": result.n_pairs,
        "factors": result.factors,
        "sectors": result.sectors,
        "sharpe_matrix": result.sharpe_matrix,
        "metrics": [dataclasses.asdict(m) for m in result.metrics],
        "note": (
            "OOS Sharpe from rolling 252-day expanding-window walk-forward. "
            "Long sector when IC estimate > 0, flat otherwise. No transaction costs assumed."
        ),
    }


@router.get("/spillover/rolling")
async def rolling_spillover_endpoint(window: int = 200, step: int = 21):
    start, end = _default_dates()
    factors = load_factor_series(["brent", "gold", "copper", "usdinr"], start, end)
    sectors = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)

    if factors.empty or sectors.empty:
        raise HTTPException(status_code=503, detail="No factor/sector data cached.")

    import pandas as pd
    combined = pd.concat([sectors, factors], axis=1).dropna()

    from src.research.diebold_yilmaz import rolling_spillover
    try:
        series = rolling_spillover(combined, window=window, step=step)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rolling spillover failed: {e}")

    if series.empty:
        raise HTTPException(status_code=503, detail="Insufficient data for rolling spillover.")

    return {
        "dates": [str(d.date()) for d in series.index],
        "values": [round(float(v), 2) for v in series.values],
        "window": window,
        "step": step,
        "note": "Rolling Diebold-Yilmaz total connectedness index (%). VAR + Pesaran-Shin GFEVD.",
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
