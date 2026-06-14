"""RiskMetrics EWMA volatility & covariance (FRM Wk7/8). Default lambda 0.94
(RiskMetrics / J.R. Varma committee for NSE daily data). Missing returns are
treated as zero (fillna(0)), which biases variance slightly downward during data
gaps -- acceptable for clean daily panels."""
from __future__ import annotations
import numpy as np
import pandas as pd


def ewma_vol(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    r = returns.fillna(0.0).to_numpy()
    var = np.empty(len(r))
    var[0] = r[0] ** 2
    for t in range(1, len(r)):
        var[t] = lam * var[t - 1] + (1 - lam) * r[t - 1] ** 2   # h_t conditional on info to t-1
    return pd.Series(np.sqrt(var), index=returns.index)


def ewma_cov(returns_df: pd.DataFrame, lam: float = 0.94) -> np.ndarray:
    """Latest EWMA covariance matrix (recursion over the sample, last state)."""
    X = returns_df.fillna(0.0).to_numpy()
    S = np.cov(X.T, ddof=1)               # seed with sample covariance
    for t in range(1, len(X)):
        x = X[t - 1].reshape(-1, 1)
        S = lam * S + (1 - lam) * (x @ x.T)
    return 0.5 * (S + S.T)                # symmetrize floating error
