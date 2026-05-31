"""Max drawdown, current drawdown, underwater chart."""
from __future__ import annotations
import pandas as pd
import numpy as np


def drawdown_series(portfolio_returns: pd.Series) -> pd.Series:
    """Cumulative drawdown from peak at each date."""
    cum = (1 + portfolio_returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return dd


def max_drawdown(portfolio_returns: pd.Series) -> dict:
    dd = drawdown_series(portfolio_returns)
    max_dd = float(dd.min())
    trough_date = dd.idxmin()

    # Find the peak before the trough
    peak_date = dd.loc[:trough_date][dd.loc[:trough_date] == 0].index[-1] \
        if (dd.loc[:trough_date] == 0).any() else dd.loc[:trough_date].index[0]

    # Recovery: first date after trough where drawdown returns to 0
    after_trough = dd.loc[trough_date:]
    recovered = after_trough[after_trough >= -0.001]
    recovery_date = recovered.index[0] if not recovered.empty else None

    current_dd = float(dd.iloc[-1])

    return {
        "max_drawdown": max_dd,
        "max_dd_start": str(peak_date.date()),
        "max_dd_end": str(trough_date.date()),
        "recovery_date": str(recovery_date.date()) if recovery_date else None,
        "current_drawdown": current_dd,
        "series": dd,
    }
