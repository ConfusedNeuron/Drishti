"""Risk routes — VaR, ES, backtest, contribution, drawdown, stress."""
from __future__ import annotations
import asyncio
import dataclasses

import numpy as np
from fastapi import APIRouter, HTTPException

from src.config import default_dates as _default_dates
from src.dashboard.routes.portfolio import get_snapshot
from src.dashboard.json_safe import clean_json
from src.risk.returns import build_return_matrix, portfolio_returns, covariance_matrix
from src.risk.var import all_var_methods
from src.risk.es import expected_shortfall
from src.risk.backtest import run_var_backtest
from src.risk.contribution import component_var
from src.risk.drawdown import max_drawdown
from src.risk.stress import run_all_scenarios

router = APIRouter()


@router.post("/summary")
async def risk_summary(confidence: float = 0.99, horizon_days: int = 10):
    snap = get_snapshot()
    start, end = _default_dates()

    returns_df, missing = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise HTTPException(status_code=503,
                            detail=f"No cached price data. Run data pull first. Missing: {missing}")

    weights_dict = snap.weights
    common = [s for s in weights_dict if s in returns_df.columns]
    if not common:
        raise HTTPException(status_code=503, detail="No overlap between portfolio and cached data.")

    w_series = {s: weights_dict[s] for s in common}
    total_w = sum(w_series.values())
    w_norm = {s: v / total_w for s, v in w_series.items()}
    port_ret = portfolio_returns(returns_df, w_norm)

    w_arr = np.array([w_norm[s] for s in common])
    cov = covariance_matrix(returns_df[common])

    # VaR — all three methods (GARCH-FHS is CPU-heavy; offload to thread)
    var_res = await asyncio.to_thread(
        all_var_methods, port_ret, w_arr, cov, snap.total_value, confidence, horizon_days
    )

    # ES
    es = expected_shortfall(port_ret, snap.total_value, confidence, horizon_days)

    # Backtest
    try:
        bt = run_var_backtest(port_ret, snap.total_value, confidence)
        bt_dict = dataclasses.asdict(bt)
    except ValueError as e:
        bt_dict = {"error": str(e)}

    # Component VaR
    contribs = component_var(w_arr, common, cov, snap.total_value, confidence)

    # Drawdown
    dd = max_drawdown(port_ret)
    dd_out = {k: v for k, v in dd.items() if k != "series"}

    # Stress
    stress = run_all_scenarios(snap)

    return clean_json({
        "portfolio_value": snap.total_value,
        "modeled_symbols": common,
        "missing_symbols": missing,
        "data_source": "Bloomberg Terminal, FRTL, IIM Calcutta",
        "var": {m: dataclasses.asdict(v) for m, v in var_res.items()},
        "expected_shortfall": dataclasses.asdict(es),
        "backtest": bt_dict,
        "top_contributors": [dataclasses.asdict(c) for c in contribs[:5]],
        "drawdown": dd_out,
        "stress_scenarios": [dataclasses.asdict(s) for s in stress],
        "annualized_volatility": float(port_ret.std() * np.sqrt(252)),
    })


@router.get("/drawdown-series")
async def drawdown_series_endpoint():
    snap = get_snapshot()
    start, end = _default_dates()
    returns_df, _ = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise HTTPException(status_code=503, detail="No cached price data.")
    port_ret = portfolio_returns(returns_df, snap.weights)
    from src.risk.drawdown import drawdown_series
    dd = drawdown_series(port_ret)
    return {"dates": [str(d.date()) for d in dd.index], "values": dd.tolist()}
