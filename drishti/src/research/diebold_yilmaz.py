"""
Diebold-Yilmaz (2012) connectedness / volatility-spillover index.

Method:
  1. Fit a VAR(p) model to the return series.
  2. Compute the H-step generalized forecast error variance decomposition
     (GFEVD, Pesaran-Shin 1998 — order-invariant, unlike Cholesky).
  3. Build the spillover table:
       spillover[i,j] = fraction of H-step FEVD of series i attributable to
                        shocks from series j  (i ≠ j → off-diagonal).
  4. Report: total connectedness, directional (to / from / net), pairwise.

References:
  Diebold & Yilmaz (2012), "Better to Give than to Receive: Predictive
    Directional Measurement of Volatility Spillovers", IJF.
  Pesaran & Shin (1998), "Generalized Impulse Response Analysis in Linear
    Multivariate Models", EL.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from statsmodels.tsa.api import VAR

from src.models import SpilloverTable


def _select_var_lag(data: np.ndarray, max_lag: int = 10) -> int:
    """Select VAR lag order using AIC (capped at max_lag)."""
    model = VAR(data)
    result = model.select_order(maxlags=max_lag, verbose=False)
    lag = result.aic
    return max(1, int(lag))


def _generalized_fevd(var_result, H: int) -> np.ndarray:
    """
    Compute generalized (Pesaran-Shin) FEVD at horizon H.
    Returns (k, k) matrix where entry [i, j] = fraction of H-step
    forecast error variance of variable i due to variable j.
    Not row-normalized — normalization done in caller.
    """
    k = var_result.neqs
    sigma = var_result.sigma_u        # (k, k) residual covariance
    coefs = var_result.coefs          # (p, k, k) AR coefficient matrices

    # Compute moving-average coefficients Ψ_h for h = 0..H-1
    p = len(coefs)
    Psi = np.zeros((H, k, k))
    Psi[0] = np.eye(k)
    for h in range(1, H):
        for j in range(min(h, p)):
            Psi[h] += coefs[j] @ Psi[h - 1 - j]

    # GFEVD: theta[i, j] = sum_{h=0}^{H-1} (e_i' Psi_h sigma e_j)^2 / sigma_jj
    #                        / (e_i' sum_{h=0}^{H-1} Psi_h sigma Psi_h' e_i)
    sigma_diag = np.diag(sigma)
    theta = np.zeros((k, k))

    for i in range(k):
        e_i = np.zeros(k)
        e_i[i] = 1.0
        denom = sum(float(e_i @ Psi[h] @ sigma @ Psi[h].T @ e_i) for h in range(H))
        for j in range(k):
            e_j = np.zeros(k)
            e_j[j] = 1.0
            numer = sum(float((e_i @ Psi[h] @ sigma @ e_j) ** 2) for h in range(H))
            theta[i, j] = numer / (sigma_diag[j] * denom) if denom > 0 else 0.0

    # Row-normalize so each row sums to 1
    row_sums = theta.sum(axis=1, keepdims=True)
    theta_norm = theta / np.where(row_sums > 0, row_sums, 1.0)
    return theta_norm


def compute_spillover(
    returns_df: pd.DataFrame,
    var_lag: int | None = None,
    fevd_horizon: int = 10,
    max_lag: int = 5,
) -> SpilloverTable:
    """
    Compute the Diebold-Yilmaz connectedness table.

    returns_df: aligned daily returns, columns = variable names
                (e.g. sector indices + commodity factors)
    """
    data = returns_df.dropna().values
    names = list(returns_df.columns)
    k = len(names)

    if var_lag is None:
        try:
            var_lag = _select_var_lag(data, max_lag=max_lag)
        except Exception:
            var_lag = 1

    model = VAR(data)
    fitted = model.fit(var_lag)

    theta = _generalized_fevd(fitted, H=fevd_horizon)

    # Off-diagonal contributions
    pairwise = pd.DataFrame(theta, index=names, columns=names)

    # Directional spillovers
    # "To i" = what fraction of other variables' forecast errors is attributable to i
    to_spillover  = {names[j]: float(np.sum(theta[:, j]) - theta[j, j]) / k * 100
                     for j in range(k)}
    # "From i" = what fraction of i's forecast error is attributable to others
    from_spillover = {names[i]: float(np.sum(theta[i, :]) - theta[i, i]) * 100
                      for i in range(k)}
    net_spillover  = {names[i]: to_spillover[names[i]] - from_spillover[names[i]]
                      for i in range(k)}

    # Total connectedness index
    off_diag_sum = float(np.sum(theta) - np.trace(theta))
    total_spillover = off_diag_sum / k * 100

    return SpilloverTable(
        total_spillover=total_spillover,
        to_spillover=to_spillover,
        from_spillover=from_spillover,
        net_spillover=net_spillover,
        pairwise=pairwise * 100,    # express as percentages
        var_lag=var_lag,
        fevd_horizon=fevd_horizon,
    )


def rolling_spillover(
    returns_df: pd.DataFrame,
    window: int = 200,
    step: int = 21,
    fevd_horizon: int = 10,
) -> pd.Series:
    """
    Rolling total connectedness index.
    Returns a Series indexed by date (end of each rolling window).
    """
    results = {}
    idx = returns_df.dropna().index
    n = len(idx)

    for end in range(window, n, step):
        sub = returns_df.iloc[end - window: end]
        try:
            tbl = compute_spillover(sub, fevd_horizon=fevd_horizon)
            results[idx[end - 1]] = tbl.total_spillover
        except Exception:
            continue

    return pd.Series(results, name="total_connectedness")
