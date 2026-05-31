"""
Three genuinely distinct VaR methods:

1. Historical simulation   — empirical quantile of actual return distribution.
   Multi-day: non-overlapping windows (not √t, which assumes i.i.d.).

2. Parametric (delta-normal) — assumes multivariate-normal returns.
   Multi-day: √t scaling is stated as an assumption, caveat shown in output.

3. GARCH-FHS (Filtered Historical Simulation) — GARCH(1,1) standardizes residuals,
   then bootstraps from them using the GARCH-forecasted volatility.
   Fat-tailed and genuinely different from parametric.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

from src.models import VaRResult


# ── 1. Historical simulation ───────────────────────────────────────────────

def historical_var(
    portfolio_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> VaRResult:
    """
    Empirical lower-tail VaR.
    Multi-day horizon: uses non-overlapping return windows (not √t scaling).
    """
    r = portfolio_returns.dropna().values

    if horizon_days > 1:
        n_windows = len(r) // horizon_days
        if n_windows < 30:
            # Fall back to √t with warning
            var_1d = np.percentile(r, (1 - confidence) * 100)
            var_hd = var_1d * np.sqrt(horizon_days)
            return VaRResult(
                amount=abs(var_hd * portfolio_value),
                percent=abs(var_hd),
                confidence=confidence,
                horizon_days=horizon_days,
                method="historical",
                obs=len(r),
                note="Fewer than 30 non-overlapping windows; √t approximation used.",
            )
        windows = [r[i * horizon_days: (i + 1) * horizon_days].sum()
                   for i in range(n_windows)]
        dist = np.array(windows)
    else:
        dist = r

    var_return = np.percentile(dist, (1 - confidence) * 100)
    return VaRResult(
        amount=abs(var_return * portfolio_value),
        percent=abs(var_return),
        confidence=confidence,
        horizon_days=horizon_days,
        method="historical",
        obs=len(dist),
    )


# ── 2. Parametric (delta-normal) ───────────────────────────────────────────

def parametric_var(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    portfolio_value: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> VaRResult:
    """
    Delta-normal VaR. Assumes multivariate-normal return distribution.
    Multi-day: √t scaling (stated assumption, caveat in output).
    """
    port_variance = float(weights @ cov_matrix @ weights)
    port_std = np.sqrt(port_variance)
    z = stats.norm.ppf(1 - confidence)   # negative, e.g. -2.326 at 99%
    var_1d = abs(z * port_std)
    var_hd = var_1d * np.sqrt(horizon_days)

    return VaRResult(
        amount=var_hd * portfolio_value,
        percent=var_hd,
        confidence=confidence,
        horizon_days=horizon_days,
        method="parametric",
        note="Assumes multivariate-normal returns; √t horizon scaling.",
    )


# ── 3. GARCH-FHS ───────────────────────────────────────────────────────────

def garch_fhs_var(
    portfolio_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
    n_bootstrap: int = 10_000,
    seed: int = 42,
) -> VaRResult:
    """
    GARCH-Filtered Historical Simulation.

    Steps:
      1. Fit GARCH(1,1) to portfolio returns.
      2. Extract standardized residuals (z_t = r_t / sigma_t).
      3. Forecast next-period conditional volatility (sigma_{T+1}).
      4. Bootstrap from z_t to simulate n_bootstrap paths.
      5. Scale by sigma_{T+1} and take empirical quantile.

    Unlike parametric VaR, this preserves the empirical tail shape
    (fat tails, skewness) while conditioning on current volatility.
    """
    try:
        from arch import arch_model
    except ImportError:
        raise RuntimeError("arch package required for GARCH-FHS: pip install arch")

    r = portfolio_returns.dropna()
    r_pct = r * 100  # arch expects percentage-scale returns

    model = arch_model(r_pct, vol="GARCH", p=1, q=1, dist="normal", rescale=False)
    res = model.fit(disp="off", show_warning=False)

    std_resid = res.std_resid.dropna().values

    # 1-step ahead conditional volatility forecast (as decimal)
    fcast = res.forecast(horizon=1, reindex=False)
    sigma_next = float(np.sqrt(fcast.variance.values[-1, 0])) / 100

    rng = np.random.default_rng(seed)

    if horizon_days == 1:
        z_sim = rng.choice(std_resid, size=n_bootstrap, replace=True)
        sim_returns = z_sim * sigma_next
    else:
        # Multi-step: bootstrap paths of length horizon_days
        # Re-simulate GARCH recursively from current parameters
        omega = res.params["omega"] / 1e4   # back to decimal² scale
        alpha = res.params["alpha[1]"]
        beta  = res.params["beta[1]"]
        sim_returns = np.zeros(n_bootstrap)
        for s in range(n_bootstrap):
            sig2 = sigma_next ** 2
            path_ret = 0.0
            for _ in range(horizon_days):
                z = rng.choice(std_resid)
                r_step = z * np.sqrt(sig2)
                path_ret += r_step
                sig2 = omega + alpha * r_step**2 + beta * sig2
            sim_returns[s] = path_ret

    var_return = np.percentile(sim_returns, (1 - confidence) * 100)
    return VaRResult(
        amount=abs(var_return * portfolio_value),
        percent=abs(var_return),
        confidence=confidence,
        horizon_days=horizon_days,
        method="garch_fhs",
        obs=len(std_resid),
        note=f"GARCH(1,1) sigma_next={sigma_next:.4%}; bootstrapped from standardized residuals.",
    )


# ── Convenience: run all three ─────────────────────────────────────────────

def all_var_methods(
    portfolio_returns: pd.Series,
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    portfolio_value: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> dict[str, VaRResult]:
    return {
        "historical":  historical_var(portfolio_returns, portfolio_value, confidence, horizon_days),
        "parametric":  parametric_var(weights, cov_matrix, portfolio_value, confidence, horizon_days),
        "garch_fhs":   garch_fhs_var(portfolio_returns, portfolio_value, confidence, horizon_days),
    }
