"""Risk-adjusted performance measures (FRM Wk3). Inputs are simple daily return
Series; rf is given annualized and converted to per-period internally."""
from __future__ import annotations
import numpy as np
import pandas as pd


def _align(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    j = pd.concat([a, b], axis=1).dropna()
    return j.iloc[:, 0], j.iloc[:, 1]


def beta(asset: pd.Series, market: pd.Series) -> float:
    a, m = _align(asset, market)
    var = np.var(m, ddof=1)
    return float(np.cov(a, m, ddof=1)[0, 1] / var) if var > 0 else np.nan


def sharpe(returns: pd.Series, rf_annual: float = 0.0, periods: int = 252) -> float:
    rf = rf_annual / periods
    ex = returns.dropna() - rf
    sd = ex.std(ddof=1)
    return float(ex.mean() / sd * np.sqrt(periods)) if sd > 0 else np.nan


def treynor(returns: pd.Series, market: pd.Series, rf_annual: float = 0.0,
            periods: int = 252) -> float:
    a, m = _align(returns, market)          # align so beta and mean use the same sample
    b = beta(returns, market)
    ann_ex = a.mean() * periods - rf_annual
    return float(ann_ex / b) if np.isfinite(b) and b != 0 else np.nan


def jensen_alpha(returns: pd.Series, market: pd.Series, rf_annual: float = 0.0,
                 periods: int = 252) -> float:
    a, m = _align(returns, market)
    b = beta(returns, market)
    rp = a.mean() * periods
    rm = m.mean() * periods
    return float(rp - (rf_annual + b * (rm - rf_annual)))
