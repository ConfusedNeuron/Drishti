"""Efficient Frontier Studio core — pure functions that prepare horizon-matched,
annualized (mu, cov) inputs for src/portfolio/frontier.py and project a portfolio's
current weights onto that space. Diagnostic only — not investment advice.

Horizon-matched frequency: short horizons compound on daily returns, medium on
weekly, long on monthly, so the estimation window and the return frequency are
consistent with the diagnostic horizon being examined.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS: dict[str, tuple[int, str]] = {
    "6m": (126, "D"),
    "1y": (252, "D"),
    "5y": (1260, "W"),
    "10y": (2520, "M"),
    "20y": (5040, "M"),
}
ANNUALIZE = {"D": 252, "W": 52, "M": 12}
MIN_OBS = {"D": 60, "W": 52, "M": 36}


def to_monthly(returns: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Compound daily simple returns into calendar-month buckets."""
    return (1 + returns).resample("ME").prod().dropna() - 1


def to_weekly_frame(returns: pd.DataFrame) -> pd.DataFrame:
    """Compound daily simple returns into W-FRI weekly buckets (frame form)."""
    return (1 + returns).resample("W-FRI").prod().dropna() - 1


def estimate_inputs(
    returns_daily: pd.DataFrame, horizon: str
) -> tuple[np.ndarray, np.ndarray, list[str], dict]:
    """Estimate an annualized (mu, cov) pair for a given diagnostic horizon.

    Slices the last `lookback` daily rows, compounds to the horizon's matched
    frequency, drops thin-history columns/rows, then shrinks the covariance
    with Ledoit-Wolf (falls back to sample covariance if shrinkage fails).
    """
    if horizon not in HORIZONS:
        raise ValueError(f"unknown horizon '{horizon}'; valid: {list(HORIZONS)}")

    lookback, freq = HORIZONS[horizon]
    sliced = returns_daily.iloc[-lookback:]

    if freq == "D":
        compounded = sliced
    elif freq == "W":
        compounded = to_weekly_frame(sliced)
    else:
        compounded = to_monthly(sliced)

    min_obs = MIN_OBS[freq]
    counts = compounded.count()
    kept_cols = counts[counts >= min_obs].index.tolist()
    dropped_symbols = sorted(set(compounded.columns) - set(kept_cols))
    cleaned = compounded[kept_cols].dropna()

    n_cols = cleaned.shape[1]
    if n_cols < 3:
        raise ValueError(
            f"need ≥3 assets after cleaning, have {n_cols} (dropped: {dropped_symbols})"
        )
    n_rows = cleaned.shape[0]
    if n_rows < min_obs:
        raise ValueError(f"need ≥{min_obs} {freq} observations, have {n_rows}")

    values = cleaned.to_numpy()
    factor = ANNUALIZE[freq]
    mu = values.mean(axis=0) * factor

    try:
        from sklearn.covariance import LedoitWolf

        lw = LedoitWolf().fit(values)
        cov = lw.covariance_ * factor
        shrinkage = float(lw.shrinkage_)
    except Exception:
        cov = np.cov(values, rowvar=False) * factor
        shrinkage = None

    symbols = cleaned.columns.tolist()
    idx = cleaned.index
    meta = {
        "frequency": freq,
        "n_obs": n_rows,
        "n_assets": n_cols,
        "dropped_symbols": dropped_symbols,
        "shrinkage": shrinkage,
        "lookback_days": lookback,
        "window_start": str(idx[0].date()),
        "window_end": str(idx[-1].date()),
    }
    return mu, cov, symbols, meta


def portfolio_point(
    weights: dict[str, float], symbols: list[str], mu: np.ndarray, cov: np.ndarray
) -> dict:
    """Project a set of holding weights onto the estimated (mu, cov) space,
    reporting the coverage gap between held symbols and the frontier universe."""
    total_abs = sum(abs(v) for v in weights.values())
    if total_abs == 0:
        return {"vol": None, "ret": None, "coverage": 0.0}

    kept = set(weights) & set(symbols)
    if not kept:
        return {"vol": None, "ret": None, "coverage": 0.0}

    coverage = sum(abs(weights[s]) for s in kept) / total_abs

    w = np.array([weights.get(s, 0.0) for s in symbols])
    w = w / w.sum()

    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    return {"vol": vol, "ret": ret, "coverage": float(coverage)}
