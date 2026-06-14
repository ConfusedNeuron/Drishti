"""Johansen cointegration test + VECM (SAAPM Wk3/4), wrapping statsmodels."""
from __future__ import annotations
import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.vecm import coint_johansen, VECM


def johansen_test(df: pd.DataFrame, det_order: int = 0, k_ar_diff: int = 1) -> dict:
    """Trace-test cointegration rank. det_order: -1 none, 0 constant, 1 linear."""
    res = coint_johansen(df.dropna(), det_order, k_ar_diff)
    trace = res.lr1                      # trace statistics
    crit95 = res.cvt[:, 1]               # 95% critical values (cvt cols = 90/95/99)
    rank = int(np.sum(trace > crit95))
    return {"trace_stat": trace.tolist(), "crit_95": crit95.tolist(),
            "rank": rank, "eig": res.eig.tolist()}


def fit_vecm(df: pd.DataFrame, k_ar_diff: int = 1, coint_rank: int = 1,
             steps: int = 5) -> pd.DataFrame:
    """Fit a VECM and return an n-step forecast as a DataFrame (cols = series)."""
    model = VECM(df.dropna(), k_ar_diff=k_ar_diff, coint_rank=coint_rank, deterministic="ci")
    fit = model.fit()
    fc = fit.predict(steps=steps)
    return pd.DataFrame(fc, columns=df.columns)
