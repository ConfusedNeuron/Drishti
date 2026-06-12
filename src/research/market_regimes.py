"""Bull/bear regime study: classical 20% rule for narrative, HMM prob overlay for statistical view."""
from __future__ import annotations
import numpy as np
import pandas as pd


def classify_bull_bear(px: pd.Series, threshold: float = 0.20) -> pd.Series:
    """20% rule: bear from peak preceding a >=threshold fall until trough preceding a >=threshold rally."""
    px = px.dropna()
    state = "bull"
    last_peak = float(px.iloc[0])
    last_trough = float(px.iloc[0])
    out = []
    for v in px:
        v = float(v)
        if state == "bull":
            last_peak = max(last_peak, v)
            if v <= last_peak * (1 - threshold):
                state = "bear"
                last_trough = v
        else:
            last_trough = min(last_trough, v)
            if v >= last_trough * (1 + threshold):
                state = "bull"
                last_peak = v
        out.append(state)
    return pd.Series(out, index=px.index)


def regime_signs(returns: pd.Series, regimes: pd.Series) -> dict:
    """Summary statistics per regime — what the data says each regime looks like."""
    out = {}
    for reg in ("bull", "bear"):
        r = returns[regimes.reindex(returns.index) == reg].dropna()
        if len(r) < 20:
            continue
        out[reg] = {
            "n_days": int(len(r)),
            "mean_daily_ret": float(r.mean()),
            "ann_vol": float(r.std() * np.sqrt(252)),
            "worst_day": float(r.min()),
            "best_day": float(r.max()),
            "skew": float(r.skew()),
            "pct_up_days": float((r > 0).mean()),
        }
    return out


def current_state(
    px: pd.Series,
    regimes: pd.Series,
    hmm_prob_high_vol: float | None = None,
    threshold: float = 0.20,
) -> dict:
    px = px.dropna()
    peak = float(px.cummax().iloc[-1])
    current = float(px.iloc[-1])
    dd = current / peak - 1
    current_regime = str(regimes.iloc[-1])
    # Distance to bear trigger (positive = still above bear threshold in bull)
    pct_to_bear = (current / peak - (1 - threshold)) if current_regime == "bull" else 0.0
    return {
        "regime": current_regime,
        "drawdown_from_peak": round(dd, 4),
        "pct_to_bear_threshold": round(pct_to_bear, 4),
        "hmm_prob_high_vol": hmm_prob_high_vol,
        "note": "Descriptive positioning vs the 20% threshold; not a forecast.",
    }
