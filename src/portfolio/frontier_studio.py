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

from src.portfolio.frontier import efficient_frontier

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


def frequency_returns(returns_daily: pd.DataFrame, horizon: str) -> tuple[pd.DataFrame, int]:
    """Slice the last `lookback` daily rows and compound to the horizon's frequency.

    Returns (frequency_frame_dropna, annualization_factor). Pure; no guards (the
    /compute route already validated the horizon and the surviving columns via
    estimate_inputs before calling this for the resampled-band step)."""
    if horizon not in HORIZONS:
        raise ValueError(f"unknown horizon '{horizon}'; valid: {list(HORIZONS)}")

    lookback, freq = HORIZONS[horizon]
    sliced = returns_daily.iloc[-lookback:]

    if freq == "D":
        frame = sliced
    elif freq == "W":
        frame = to_weekly_frame(sliced)
    else:
        frame = to_monthly(sliced)

    return frame.dropna(), ANNUALIZE[freq]


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


def _round_weights(weights: np.ndarray, symbols: list[str]) -> dict[str, float]:
    """Payload weight convention: round to 6dp, drop entries with |w| < 1e-4."""
    return {
        symbols[j]: round(float(weights[j]), 6)
        for j in range(len(symbols))
        if abs(weights[j]) >= 1e-4
    }


def resampled_band(
    returns_freq: pd.DataFrame,
    ret_grid: np.ndarray,
    rf: float,
    long_only: bool,
    factor: int,
    n_boot: int = 50,
    seed: int = 42,
) -> dict:
    """Estimation-uncertainty band around the frontier via iid row-bootstrap.

    NOTE (deviation from design): the design's parameter list omits an
    annualization factor, but `returns_freq` here is per-period (not
    annualized) and the caller-side frequency->factor mapping (252/52/12)
    cannot be recovered from the frame alone — so `factor` is an added,
    required parameter (caller passes ANNUALIZE[meta["frequency"]]).
    """
    n_boot = min(n_boot, 100)
    rng = np.random.default_rng(seed)
    values = returns_freq.values
    n = len(values)

    rows = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample = values[idx]

        mu_b = sample.mean(axis=0) * factor
        try:
            from sklearn.covariance import LedoitWolf

            cov_b = LedoitWolf().fit(sample).covariance_ * factor
        except Exception:
            cov_b = np.cov(sample, rowvar=False) * factor

        fr = efficient_frontier(mu_b, cov_b, n_points=len(ret_grid), long_only=long_only)
        risk_row = np.interp(ret_grid, fr["ret"], fr["risk"], left=np.nan, right=np.nan)
        out_of_range = (ret_grid < fr["ret"].min()) | (ret_grid > fr["ret"].max())
        risk_row = np.where(out_of_range, np.nan, risk_row)
        rows.append(risk_row)

    stack = np.vstack(rows)
    with np.errstate(invalid="ignore"):
        risk_lo = np.nanpercentile(stack, 10, axis=0)
        risk_hi = np.nanpercentile(stack, 90, axis=0)

    return {
        "ret": np.asarray(ret_grid),
        "risk_lo": risk_lo,
        "risk_hi": risk_hi,
        "n_boot": int(n_boot),
        "note": "iid row bootstrap; ignores return autocorrelation (a documented limitation)",
    }


def risk_presets(frontier: dict, tang_vol: float, symbols: list[str]) -> list[dict]:
    """Three risk-level anchor points (conservative/balanced/aggressive) located
    on the frontier by nearest-vol match to 0.6x/1.0x/1.4x tangency vol.

    NOTE (deviation from design): `symbols` is an added required parameter —
    the design's signature had no way to translate `frontier["weights"]` (bare
    arrays) into a symbol->weight dict without it.
    """
    risk = frontier["risk"]
    ret = frontier["ret"]
    weights = frontier["weights"]
    lo_r, hi_r = float(risk.min()), float(risk.max())

    labels = ["conservative", "balanced", "aggressive"]
    targets = [min(max(m * tang_vol, lo_r), hi_r) for m in (0.6, 1.0, 1.4)]

    presets = []
    for label, target in zip(labels, targets):
        idx = int(np.argmin(np.abs(risk - target)))
        presets.append({
            "label": label,
            "vol": float(risk[idx]),
            "ret": float(ret[idx]),
            "weights": _round_weights(weights[idx], symbols),
        })
    return presets


def weight_gap(current: dict[str, float], target: dict[str, float]) -> list[dict]:
    """Diagnostic comparison of current vs target weight maps — reports the
    gap vs the optimizer's point, not a trade recommendation."""
    symbols = {
        s for s in set(current) | set(target)
        if abs(current.get(s, 0.0)) > 0.001 or abs(target.get(s, 0.0)) > 0.001
    }

    rows = []
    for s in symbols:
        c = float(current.get(s, 0.0))
        t = float(target.get(s, 0.0))
        rows.append({
            "symbol": s,
            "current": round(c, 6),
            "target": round(t, 6),
            "delta": round(t - c, 6),
        })

    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return rows
