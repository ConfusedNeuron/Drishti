"""
DCC-GARCH (Dynamic Conditional Correlation) — 2-step Engle (2002) estimator.

Step 1: Fit univariate GARCH(1,1) to each return series. Extract standardized residuals.
Step 2: Estimate DCC parameters (α, β) from the correlation dynamics of standardized residuals.
        Q_t = (1-α-β)*Q̄ + α*(z_{t-1} z_{t-1}') + β*Q_{t-1}
        R_t = diag(Q_t)^{-1/2} * Q_t * diag(Q_t)^{-1/2}

Output: time-varying conditional correlations between each (sector, commodity/macro) pair.
These are the primary spillover evidence: correlation spikes during COVID-2020, 2022.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _fit_garch11(series: pd.Series) -> tuple[np.ndarray, float]:
    """
    Fit GARCH(1,1) to a return series.
    Returns (standardized_residuals, annualized_unconditional_vol).
    """
    from arch import arch_model

    r_pct = series.dropna() * 100
    model = arch_model(r_pct, vol="GARCH", p=1, q=1, dist="normal", rescale=False)
    res = model.fit(disp="off", show_warning=False)
    std_resid = res.std_resid.dropna().values
    uncond_vol = float(np.sqrt(res.params["omega"] /
                               (1 - res.params["alpha[1]"] - res.params["beta[1]"]))) / 100
    return std_resid, uncond_vol


def _dcc_log_likelihood(params: np.ndarray,
                         std_resid_matrix: np.ndarray) -> float:
    """Negative log-likelihood for DCC parameters (α, β)."""
    alpha, beta = params
    if alpha <= 0 or beta <= 0 or alpha + beta >= 1:
        return 1e10

    T, k = std_resid_matrix.shape
    Q_bar = np.cov(std_resid_matrix.T)

    Q = Q_bar.copy()
    ll = 0.0

    for t in range(1, T):
        z = std_resid_matrix[t - 1, :]
        Q = (1 - alpha - beta) * Q_bar + alpha * np.outer(z, z) + beta * Q
        Q_diag_inv = np.diag(1.0 / np.sqrt(np.diag(Q)))
        R = Q_diag_inv @ Q @ Q_diag_inv
        # Ensure positive definiteness
        R = (R + R.T) / 2
        try:
            sign, logdet = np.linalg.slogdet(R)
            if sign <= 0:
                return 1e10
            z_t = std_resid_matrix[t, :]
            R_inv = np.linalg.inv(R)
            ll += -0.5 * (logdet + z_t @ R_inv @ z_t - z_t @ z_t)
        except np.linalg.LinAlgError:
            return 1e10

    return -ll


def fit_dcc_garch(
    returns_df: pd.DataFrame,
    n_dcc_iter: int = 50,
) -> dict:
    """
    Fit DCC-GARCH to a DataFrame of return series (columns = assets).
    Returns time-varying correlation matrix at each date.

    returns_df: aligned daily returns, columns = asset names
    """
    # Step 1: Fit GARCH(1,1) per series, collect standardized residuals
    std_resids = {}
    uncond_vols = {}
    dates = None

    for col in returns_df.columns:
        series = returns_df[col].dropna()
        z, uv = _fit_garch11(series)
        # Align lengths — std_resid may be shorter due to initial GARCH period
        std_resids[col] = z
        uncond_vols[col] = uv

    # Trim all to same length (min length)
    min_len = min(len(v) for v in std_resids.values())
    Z = np.column_stack([v[-min_len:] for v in std_resids.values()])
    col_names = list(std_resids.keys())

    # Get corresponding dates
    common_idx = returns_df.dropna().index[-min_len:]

    # Step 2: Estimate DCC parameters
    result = minimize(
        _dcc_log_likelihood,
        x0=[0.01, 0.95],
        args=(Z,),
        method="L-BFGS-B",
        bounds=[(1e-6, 0.3), (1e-6, 0.99)],
        options={"maxiter": n_dcc_iter},
    )
    alpha, beta = result.x

    # Step 3: Compute full time-varying correlation sequence
    T, k = Z.shape
    Q_bar = np.cov(Z.T)
    Q = Q_bar.copy()

    correlation_series = {f"{col_names[i]}_{col_names[j]}": []
                          for i in range(k) for j in range(i + 1, k)}
    date_list = []

    for t in range(1, T):
        z = Z[t - 1, :]
        Q = (1 - alpha - beta) * Q_bar + alpha * np.outer(z, z) + beta * Q
        Q_diag_inv = np.diag(1.0 / np.sqrt(np.diag(Q)))
        R = Q_diag_inv @ Q @ Q_diag_inv

        date_list.append(common_idx[t])
        for i in range(k):
            for j in range(i + 1, k):
                pair = f"{col_names[i]}_{col_names[j]}"
                correlation_series[pair].append(float(R[i, j]))

    corr_df = pd.DataFrame(correlation_series, index=date_list)

    return {
        "correlations": corr_df,          # time-varying pairwise correlations
        "dcc_alpha": float(alpha),
        "dcc_beta": float(beta),
        "unconditional_vols": uncond_vols,
        "column_names": col_names,
        "Q_bar": Q_bar,
    }


def crisis_correlation_summary(corr_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare average correlations in crisis vs. normal periods.
    Crisis windows: COVID Feb-Apr 2020, Russia-Ukraine Jan-Mar 2022.
    """
    windows = {
        "covid_2020":  ("2020-02-01", "2020-04-30"),
        "crisis_2022": ("2022-01-01", "2022-03-31"),
        "normal":      ("2021-06-01", "2021-12-31"),
    }

    rows = []
    for period, (start, end) in windows.items():
        sub = corr_df.loc[start:end]
        if sub.empty:
            continue
        row = {"period": period}
        row.update(sub.mean().to_dict())
        rows.append(row)

    return pd.DataFrame(rows).set_index("period")
