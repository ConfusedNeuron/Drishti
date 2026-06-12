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


def _fit_garch11(series: pd.Series) -> tuple[pd.Series, float]:
    """
    Fit GARCH(1,1) to a return series.
    Returns (standardized_residuals as a date-indexed Series, annualized_unconditional_vol).
    """
    from arch import arch_model

    r_pct = series.dropna() * 100
    model = arch_model(r_pct, vol="GARCH", p=1, q=1, dist="normal", rescale=False)
    res = model.fit(disp="off", show_warning=False)
    std_resid = res.std_resid.dropna()          # date-indexed Series (was .values)
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


def _adcc_log_likelihood(params: np.ndarray, Z: np.ndarray, N_bar: np.ndarray, Q_bar: np.ndarray) -> float:
    """
    Negative log-likelihood for ADCC parameters (a, b, g).

    ADCC Q recursion (Cappiello-Engle-Sheppard 2006):
        n_t = z_t ⊙ 1[z_t < 0]
        Q_t = (1-a-b)*Q̄ - g*N̄ + a*z_{t-1}z_{t-1}' + b*Q_{t-1} + g*n_{t-1}n_{t-1}'

    The -g*N̄ intercept correction ensures E[Q_t] = Q̄ under stationarity.
    Sufficient stationarity condition: a + b + g < 1.
    """
    a, b, g = params
    if a <= 0 or b <= 0 or g < 0 or a + b + g >= 1:
        return 1e10
    T, k = Z.shape
    Q = Q_bar.copy()
    ll = 0.0
    for t in range(1, T):
        z_prev = Z[t - 1, :]
        n_prev = np.where(z_prev < 0, z_prev, 0.0)
        Q = (1 - a - b) * Q_bar - g * N_bar + a * np.outer(z_prev, z_prev) + b * Q + g * np.outer(n_prev, n_prev)
        Q_diag_inv = np.diag(1.0 / np.sqrt(np.maximum(np.diag(Q), 1e-12)))
        R = Q_diag_inv @ Q @ Q_diag_inv
        R = (R + R.T) / 2
        try:
            sign, logdet = np.linalg.slogdet(R)
            if sign <= 0:
                return 1e10
            z_t = Z[t, :]
            R_inv = np.linalg.inv(R)
            ll += -0.5 * (logdet + z_t @ R_inv @ z_t - z_t @ z_t)
        except np.linalg.LinAlgError:
            return 1e10
    return -ll


def _adcc_grid_fallback(Z: np.ndarray, N_bar: np.ndarray, Q_bar: np.ndarray) -> tuple[float, float, float]:
    """
    Fallback: grid-search g over [0, 0.05, 0.10, 0.15]; re-optimise (a,b) at each g.
    Picks the g with lowest NLL.  Used when the joint 3-parameter optimizer fails.
    """
    best_nll = np.inf
    best_params = (0.01, 0.95, 0.0)
    for g_try in [0.0, 0.05, 0.10, 0.15]:
        def _nll_fixed_g(ab: np.ndarray) -> float:
            return _adcc_log_likelihood(np.array([ab[0], ab[1], g_try]), Z, N_bar, Q_bar)
        res = minimize(
            _nll_fixed_g,
            x0=[0.01, 0.95],
            method="L-BFGS-B",
            bounds=[(1e-6, 0.3), (1e-6, 0.99 - g_try - 1e-6)],
        )
        if res.fun < best_nll:
            best_nll = res.fun
            best_params = (float(res.x[0]), float(res.x[1]), float(g_try))
    return best_params


def fit_dcc_garch(
    returns_df: pd.DataFrame,
    n_dcc_iter: int = 50,
    asymmetric: bool = False,
) -> dict:
    """
    Fit DCC-GARCH (or ADCC) to a DataFrame of return series (columns = assets).
    Returns time-varying correlation matrix at each date.

    returns_df:  aligned daily returns, columns = asset names
    asymmetric:  if True, fit ADCC (Cappiello-Engle-Sheppard 2006) which adds a
                 negative-return asymmetry term g.  Return dict includes a "params"
                 key with {"a", "b", "g"}.  If False (default), fits standard DCC
                 and the return dict keeps "dcc_alpha" / "dcc_beta" keys.
    """
    # Step 1: Fit GARCH(1,1) per series, collect date-indexed standardized residuals
    std_resids = {}
    uncond_vols = {}

    for col in returns_df.columns:
        z, uv = _fit_garch11(returns_df[col])
        std_resids[col] = z
        uncond_vols[col] = uv

    # Align residuals on their COMMON DATES (inner join), not by position — series
    # can drop different leading/interior samples during GARCH fitting, so positional
    # trimming would silently pair different calendar dates across assets.
    Z_df = pd.concat(std_resids, axis=1).dropna()
    Z = Z_df.values
    col_names = list(Z_df.columns)
    common_idx = Z_df.index

    # Step 2: Estimate DCC / ADCC parameters
    T, k = Z.shape
    Q_bar = np.cov(Z.T)

    if asymmetric:
        # ADCC: negative shocks drive larger correlation increases than positive ones.
        # N̄ = sample mean of outer products of negative-clipped residuals.
        N_bar = np.mean(
            [np.outer(np.where(z < 0, z, 0.0), np.where(z < 0, z, 0.0)) for z in Z],
            axis=0,
        )
        adcc_result = minimize(
            _adcc_log_likelihood,
            x0=[0.01, 0.95, 0.05],
            args=(Z, N_bar, Q_bar),
            method="L-BFGS-B",
            bounds=[(1e-6, 0.3), (1e-6, 0.99), (0.0, 0.3)],
            options={"maxiter": n_dcc_iter},
        )
        if not adcc_result.success:
            # Grid-search fallback: sweep g ∈ {0, 0.05, 0.10, 0.15}, re-optimise (a,b)
            # at each value and pick the g with lowest negative log-likelihood.
            a, b, g = _adcc_grid_fallback(Z, N_bar, Q_bar)
        else:
            a, b, g = float(adcc_result.x[0]), float(adcc_result.x[1]), float(adcc_result.x[2])

        # Step 3: ADCC correlation sequence
        Q = Q_bar.copy()
        correlation_series = {f"{col_names[i]}_{col_names[j]}": []
                              for i in range(k) for j in range(i + 1, k)}
        date_list = []

        for t in range(1, T):
            z_prev = Z[t - 1, :]
            n_prev = np.where(z_prev < 0, z_prev, 0.0)
            Q = (1 - a - b) * Q_bar - g * N_bar + a * np.outer(z_prev, z_prev) + b * Q + g * np.outer(n_prev, n_prev)
            Q_diag_inv = np.diag(1.0 / np.sqrt(np.maximum(np.diag(Q), 1e-12)))
            R = Q_diag_inv @ Q @ Q_diag_inv

            date_list.append(common_idx[t])
            for i in range(k):
                for j in range(i + 1, k):
                    pair = f"{col_names[i]}_{col_names[j]}"
                    correlation_series[pair].append(float(R[i, j]))

        corr_df = pd.DataFrame(correlation_series, index=date_list)

        return {
            "correlations": corr_df,
            "params": {"a": a, "b": b, "g": g},
            "unconditional_vols": uncond_vols,
            "column_names": col_names,
            "Q_bar": Q_bar,
        }

    else:
        # Standard DCC (Engle 2002) — backward-compatible path
        result = minimize(
            _dcc_log_likelihood,
            x0=[0.01, 0.95],
            args=(Z,),
            method="L-BFGS-B",
            bounds=[(1e-6, 0.3), (1e-6, 0.99)],
            options={"maxiter": n_dcc_iter},
        )
        alpha, beta = result.x

        # Step 3: Standard DCC correlation sequence
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
