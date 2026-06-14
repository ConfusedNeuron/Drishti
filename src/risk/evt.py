"""Extreme Value Theory VaR/ES via Peaks-Over-Threshold + Generalized Pareto
(FRM Wk8, McNeil-Frey methodology). Works on the loss tail (losses = -returns).
VaR/ES returned as positive loss magnitudes."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import genpareto

MIN_EXCEEDANCES = 10   # GPD MLE is unreliable below this; also avoids genpareto.fit crash on empty tail


def fit_pot(returns: pd.Series, threshold_q: float = 0.95):
    """Fit GPD to losses exceeding the threshold_q quantile of the loss series.
    Returns (u, xi, beta, n, n_exceed). xi/beta are NaN if too few exceedances."""
    losses = -returns.dropna().to_numpy()
    u = float(np.quantile(losses, threshold_q))
    exc = losses[losses > u] - u
    n, nu = len(losses), len(exc)
    if nu < MIN_EXCEEDANCES or u <= 0:       # guard BEFORE genpareto.fit; u<=0 means no real loss tail
        return u, float("nan"), float("nan"), n, nu
    xi, _, beta = genpareto.fit(exc, floc=0.0)
    return u, float(xi), float(beta), n, nu


def evt_var(returns: pd.Series, q: float = 0.99, threshold_q: float = 0.95) -> float:
    if q < threshold_q:                      # POT only extrapolates INTO the tail beyond u
        raise ValueError("q must be >= threshold_q for POT tail extrapolation")
    u, xi, beta, n, nu = fit_pot(returns, threshold_q)
    if nu < MIN_EXCEEDANCES or not np.isfinite(xi) or xi == 0:
        return float("nan")
    return float(u + (beta / xi) * (((n / nu) * (1 - q)) ** (-xi) - 1))


def evt_es(returns: pd.Series, q: float = 0.99, threshold_q: float = 0.95) -> float:
    if q < threshold_q:
        raise ValueError("q must be >= threshold_q for POT tail extrapolation")
    u, xi, beta, n, nu = fit_pot(returns, threshold_q)
    var = evt_var(returns, q, threshold_q)
    if not np.isfinite(var) or xi >= 1:      # ES infinite/undefined for xi >= 1
        return float("nan")
    return float((var + (beta - xi * u)) / (1 - xi))
