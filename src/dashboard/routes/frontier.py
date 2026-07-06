"""Efficient Frontier Studio routes — thin orchestration over
src/portfolio/frontier_studio.py and src/portfolio/frontier.py.
Diagnostic only — not investment advice."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from src.config import default_dates as _default_dates
from src.dashboard import route_cache
from src.dashboard.json_safe import clean_json
from src.dashboard.routes.portfolio import get_snapshot
from src.portfolio.frontier import efficient_frontier, min_variance, tangency
from src.portfolio.frontier_studio import (
    estimate_inputs,
    frequency_returns,
    portfolio_point,
    resampled_band,
    risk_presets,
    weight_gap,
)
from src.research.series_io import load_macro_prices
from src.research.universe import load_sectors, load_universe, load_v2_returns
from src.risk.returns import build_return_matrix

router = APIRouter()


@lru_cache(maxsize=1)
def _universe_list() -> list[dict]:
    manifest = load_universe()
    if not manifest:
        return []                      # empty → route raises 503
    sectors = load_sectors()
    rows = []
    for full in manifest:              # full == "RELIANCE IS Equity"
        sym = full.replace(" IS Equity", "")
        rows.append({"symbol": sym, "sector": sectors.get(full, "Unknown")})
    return sorted(rows, key=lambda r: r["symbol"])


@router.get("/universe")
async def universe():
    rows = _universe_list()
    if not rows:
        raise HTTPException(status_code=503, detail="Universe manifest missing; run the v2 data pull.")
    return {"candidates": rows, "count": len(rows)}


class ComputeBody(BaseModel):
    horizon: str = "1y"
    long_only: bool = True
    candidates: list[str] = []
    point: str | float = "tangency"     # "tangency" | "minvar" | float target_vol

    @field_validator("point", mode="before")
    @classmethod
    def _reject_bool_point(cls, v):
        # Runs before str|float smart-union coercion, which would otherwise turn
        # JSON true/false into 1.0/0.0 and hit the target_vol branch. A bool point
        # is meaningless here → fall through to the tangency default.
        if isinstance(v, bool):
            return "tangency"
        return v


def _wdict(w_arr: np.ndarray, symbols: list[str]) -> dict[str, float]:
    return {symbols[j]: round(float(w_arr[j]), 6) for j in range(len(symbols)) if abs(w_arr[j]) >= 1e-4}


@router.post("/compute")
async def compute(body: ComputeBody):
    snap = get_snapshot()
    start, end = _default_dates()
    daily, missing = build_return_matrix(snap, start, end)
    if daily.empty:
        raise HTTPException(status_code=503, detail="No cached price data for the loaded portfolio.")

    cache_key = (
        "frontier", snap.portfolio_id, snap.as_of, body.horizon, body.long_only,
        tuple(sorted(body.candidates)), f"{type(body.point).__name__}:{body.point}",
    )
    cached = route_cache.get(cache_key)
    if cached is not None:
        return cached

    held_upper = {c.upper() for c in daily.columns}
    cand = [c for c in dict.fromkeys(body.candidates) if c.upper() not in held_upper]
    tickers = [f"{c} IS Equity" for c in cand]

    cand_ret = load_v2_returns(tickers)
    cand_ret.columns = [col.replace(" IS Equity", "") for col in cand_ret.columns]
    unknown = [c for c in cand if c not in cand_ret.columns]
    merged = daily.join(cand_ret, how="outer")

    if merged.shape[1] > 30:
        raise HTTPException(status_code=422, detail="too many assets after merge; drop candidates (cap 30)")

    try:
        mu, cov, symbols, est_meta = estimate_inputs(merged, body.horizon)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    rf_fallback = False
    try:
        gs = load_macro_prices(["GIND10YR Index"]).dropna()
        rf = float(gs.iloc[-1, 0]) / 100.0 if not gs.empty else None
    except Exception:
        rf = None
    if rf is None or not math.isfinite(rf):
        rf = 0.065
        rf_fallback = True

    fr = efficient_frontier(mu, cov, n_points=40, long_only=body.long_only)

    tw = tangency(mu, cov, rf, body.long_only)
    t_ret = float(tw @ mu)
    t_vol = float(np.sqrt(tw @ cov @ tw))
    t_sharpe = (t_ret - rf) / t_vol if t_vol > 0 else None

    mw = min_variance(cov, body.long_only)
    m_ret = float(mw @ mu)
    m_vol = float(np.sqrt(mw @ cov @ mw))

    current = portfolio_point(snap.weights, symbols, mu, cov)

    freq_frame, factor = frequency_returns(merged[symbols], body.horizon)
    band = resampled_band(freq_frame, fr["ret"], rf, body.long_only, factor, n_boot=50, seed=42)

    presets = risk_presets(fr, t_vol, symbols)
    cml = {"rf": rf, "vol": t_vol, "ret": t_ret, "sharpe": t_sharpe}

    p = body.point
    if isinstance(p, str) and p == "minvar":
        sel_w, kind, s_vol, s_ret = mw, "minvar", m_vol, m_ret
    elif isinstance(p, (int, float)) and not isinstance(p, bool):
        target = float(p)
        idx = int(np.argmin(np.abs(fr["risk"] - target)))
        sel_w, kind = fr["weights"][idx], "target_vol"
        s_vol, s_ret = float(fr["risk"][idx]), float(fr["ret"][idx])
    else:
        sel_w, kind, s_vol, s_ret = tw, "tangency", t_vol, t_ret
    selected_weights = _wdict(sel_w, symbols)

    cw = {s: snap.weights[s] for s in symbols if s in snap.weights}
    tot = sum(cw.values())
    current_norm = {s: v / tot for s, v in cw.items()} if tot else {}
    gap = weight_gap(current_norm, selected_weights)

    meta = {
        **est_meta,
        "horizon": body.horizon,
        "long_only": body.long_only,
        "candidates_added": [c for c in cand if c in cand_ret.columns],
        "unknown_candidates": unknown,
        "missing_symbols": missing,
        "rf": rf,
        "rf_fallback": rf_fallback,
        "rf_note": "10y G-sec yield used as rf proxy at all horizons; 91-day T-bill planned.",
    }

    payload = clean_json({
        "frontier": {"risk": fr["risk"], "ret": fr["ret"]},
        "band": band,
        "current": current,
        "tangency": {"vol": t_vol, "ret": t_ret, "sharpe": t_sharpe, "weights": _wdict(tw, symbols)},
        "minvar": {"vol": m_vol, "ret": m_ret, "weights": _wdict(mw, symbols)},
        "cml": cml,
        "presets": presets,
        "selected": {"kind": kind, "vol": s_vol, "ret": s_ret, "weights": selected_weights},
        "gap": gap,
        "meta": meta,
        "disclaimer": "For educational risk analytics only. Not investment advice.",
    })
    route_cache.put(cache_key, payload)
    return payload
