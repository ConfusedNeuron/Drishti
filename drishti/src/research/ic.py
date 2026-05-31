"""
Time-series IC and Granger causality for commodity factor → sector return lead-lag.

IMPORTANT design note:
  A single commodity return (e.g. Brent day t) is a scalar identical for all
  stocks, so cross-sectional rank-correlation is undefined/trivially 0.
  We therefore compute TIME-SERIES correlation between the lagged factor return
  and the target (sector index or portfolio) return.

  IC here = rolling Pearson correlation(factor_{t-lag}, target_t) averaged over time.
  This is an economically valid lead-lag measurement.

Benjamini-Hochberg FDR correction is applied across all (factor × target × lag)
combinations to control false discovery rate.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

from src.models import GrangerResult, ICResult


def time_series_ic(
    factor_returns: pd.Series,
    target_returns: pd.Series,
    lag: int,
    rolling_window: int = 63,
) -> ICResult:
    """
    Compute rolling Pearson correlation between lagged factor and target.
    Returns mean IC, std IC, ICIR, t-stat, p-value.
    """
    factor_name = factor_returns.name or "factor"
    target_name = target_returns.name or "target"

    # Align on common dates
    df = pd.concat([factor_returns.rename("factor"), target_returns.rename("target")],
                   axis=1).dropna()

    # Shift factor by lag (use factor at t-lag to predict target at t)
    df["factor_lagged"] = df["factor"].shift(lag)
    df = df.dropna()

    if len(df) < rolling_window + lag + 10:
        return ICResult(
            factor=factor_name, target=target_name, lag_days=lag,
            ic_mean=0.0, ic_std=0.0, icir=0.0,
            t_stat=0.0, p_value=1.0, significant=False,
        )

    # Rolling IC
    ic_series = df["factor_lagged"].rolling(rolling_window).corr(df["target"]).dropna()

    ic_mean = float(ic_series.mean())
    ic_std = float(ic_series.std())
    n = len(ic_series)
    icir = ic_mean / ic_std if ic_std > 0 else 0.0
    t_stat = icir * np.sqrt(n)
    p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1)))

    return ICResult(
        factor=factor_name,
        target=target_name,
        lag_days=lag,
        ic_mean=ic_mean,
        ic_std=ic_std,
        icir=icir,
        t_stat=t_stat,
        p_value=p_value,
        significant=abs(t_stat) > 1.96,
    )


def granger_test(
    factor_returns: pd.Series,
    target_returns: pd.Series,
    max_lag: int = 10,
) -> list[GrangerResult]:
    """
    Granger causality: does lagged factor improve prediction of target
    beyond the target's own lags?

    Uses statsmodels grangercausalitytests.
    Returns one GrangerResult per lag (1 to max_lag).
    """
    from statsmodels.tsa.stattools import grangercausalitytests

    factor_name = factor_returns.name or "factor"
    target_name = target_returns.name or "target"

    df = pd.concat([target_returns.rename("target"),
                    factor_returns.rename("factor")], axis=1).dropna()

    if len(df) < max_lag * 5 + 20:
        return []

    try:
        gc = grangercausalitytests(df[["target", "factor"]].values,
                                   maxlag=max_lag, verbose=False)
    except Exception:
        return []

    results = []
    for lag, test_dict in gc.items():
        # Use F-test result
        f_stat = float(test_dict[0]["ssr_ftest"][0])
        p_val  = float(test_dict[0]["ssr_ftest"][1])
        results.append(GrangerResult(
            factor=factor_name,
            target=target_name,
            lag=lag,
            f_stat=f_stat,
            p_value=p_val,
            significant=p_val < 0.05,
        ))

    return results


def run_full_ic_study(
    factor_returns_df: pd.DataFrame,
    target_returns_df: pd.DataFrame,
    lags: list[int] | None = None,
    max_granger_lag: int = 10,
    rolling_window: int = 63,
) -> dict:
    """
    Run IC and Granger for all (factor, target, lag) combinations.
    Applies Benjamini-Hochberg FDR correction to IC p-values.

    Returns:
      ic_results   — list of ICResult
      granger_results — list of GrangerResult
    """
    if lags is None:
        lags = [1, 2, 3, 5, 10]

    ic_results: list[ICResult] = []
    granger_results: list[GrangerResult] = []

    for factor_name in factor_returns_df.columns:
        f_series = factor_returns_df[factor_name].rename(factor_name)

        for target_name in target_returns_df.columns:
            t_series = target_returns_df[target_name].rename(target_name)

            for lag in lags:
                ic = time_series_ic(f_series, t_series, lag, rolling_window)
                ic_results.append(ic)

            gc_list = granger_test(f_series, t_series, max_granger_lag)
            granger_results.extend(gc_list)

    # Benjamini-Hochberg FDR correction on IC p-values
    if ic_results:
        p_values = np.array([r.p_value for r in ic_results])
        bh_mask = _bh_correction(p_values, alpha=0.05)
        for i, r in enumerate(ic_results):
            r.bh_significant = bool(bh_mask[i])

    # Sort by |t_stat| descending
    ic_results.sort(key=lambda x: abs(x.t_stat), reverse=True)

    return {
        "ic_results": ic_results,
        "granger_results": granger_results,
        "n_tests": len(ic_results),
    }


def _bh_correction(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg FDR correction. Returns boolean mask of discoveries."""
    n = len(p_values)
    sorted_idx = np.argsort(p_values)
    sorted_p = p_values[sorted_idx]
    thresholds = np.arange(1, n + 1) * alpha / n
    below = sorted_p <= thresholds
    if below.any():
        max_k = np.where(below)[0][-1]
        discoveries = np.zeros(n, dtype=bool)
        discoveries[sorted_idx[:max_k + 1]] = True
    else:
        discoveries = np.zeros(n, dtype=bool)
    return discoveries
