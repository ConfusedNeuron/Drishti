"""
VaR backtesting: Kupiec unconditional coverage + Christoffersen independence.

References:
  Kupiec (1995) — likelihood ratio test for violation rate.
  Christoffersen (1998) — independence test for violation clustering.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

from src.models import BacktestResult, ChristoffersenResult, KupiecResult


def run_var_backtest(
    portfolio_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.99,
    rolling_window: int = 252,
) -> BacktestResult:
    """
    Roll a historical VaR estimate across time. For each day outside the
    initial window, record whether the realized return exceeded the VaR.

    portfolio_returns: full daily return series (decimal, e.g. -0.021)
    portfolio_value:   current portfolio value (for display only)
    """
    r = portfolio_returns.dropna().values
    n = len(r)

    if n < rolling_window + 30:
        raise ValueError(
            f"Need at least {rolling_window + 30} observations for backtesting; got {n}."
        )

    alpha = 1 - confidence
    violations = []
    for t in range(rolling_window, n):
        window = r[t - rolling_window: t]
        var_threshold = np.percentile(window, alpha * 100)  # negative number
        actual = r[t]
        violations.append(1 if actual < var_threshold else 0)

    v_arr = np.array(violations)
    n_obs = len(v_arr)
    n_violations = int(v_arr.sum())

    kupiec = _kupiec_test(n_violations, n_obs, confidence)
    christo = _christoffersen_test(v_arr)

    # Verdict
    if kupiec.pass_ and christo.pass_:
        verdict = "Model passes both coverage and independence tests."
    elif kupiec.pass_ and not christo.pass_:
        verdict = ("Unconditional coverage acceptable; violations cluster — "
                   "consider GARCH or regime-conditioned VaR.")
    elif not kupiec.pass_ and christo.pass_:
        verdict = "VaR systematically too optimistic — recalibrate confidence level."
    else:
        verdict = "Model fails both tests — unreliable; switch to GARCH-FHS or regime-conditioned VaR."

    return BacktestResult(
        confidence=confidence,
        obs=n_obs,
        violations=n_violations,
        kupiec=kupiec,
        christoffersen=christo,
        verdict=verdict,
    )


def _kupiec_test(violations: int, n_obs: int, confidence: float) -> KupiecResult:
    p = 1 - confidence   # expected violation probability
    v = violations
    n = n_obs

    if v == 0:
        lr = -2 * n * np.log(1 - p)
    elif v == n:
        lr = -2 * n * np.log(p)
    else:
        lr = -2 * (
            (n - v) * np.log(1 - p) + v * np.log(p) -
            (n - v) * np.log(1 - v / n) - v * np.log(v / n)
        )

    p_value = float(1 - stats.chi2.cdf(lr, df=1))
    return KupiecResult(
        lr_statistic=float(lr),
        p_value=p_value,
        pass_=p_value > 0.05,
        violations=v,
        expected_violations=round(n * p, 2),
        violation_rate=round(v / n, 4),
        expected_rate=p,
    )


def _christoffersen_test(violation_series: np.ndarray) -> ChristoffersenResult:
    v = violation_series.astype(int)

    n00 = int(((v[:-1] == 0) & (v[1:] == 0)).sum())
    n01 = int(((v[:-1] == 0) & (v[1:] == 1)).sum())
    n10 = int(((v[:-1] == 1) & (v[1:] == 0)).sum())
    n11 = int(((v[:-1] == 1) & (v[1:] == 1)).sum())

    pi01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
    pi11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
    pi   = (n01 + n11) / len(v) if len(v) > 0 else 0.0

    def _log(x: float) -> float:
        return np.log(max(x, 1e-10))

    lr_ind = -2 * (
        (n00 + n10) * _log(1 - pi) + (n01 + n11) * _log(pi)
        - n00 * _log(1 - pi01) - n01 * _log(pi01)
        - n10 * _log(1 - pi11) - n11 * _log(pi11)
    )

    p_value = float(1 - stats.chi2.cdf(lr_ind, df=1))
    clustering = pi11 > pi01
    finding = (
        "Violations cluster — model underestimates volatility persistence."
        if clustering else
        "Violations appear independent."
    )

    return ChristoffersenResult(
        lr_statistic=float(lr_ind),
        p_value=p_value,
        pass_=p_value > 0.05,
        pi01=pi01,
        pi11=pi11,
        finding=finding,
    )
