"""Expected Shortfall (Conditional VaR / CVaR)."""
from __future__ import annotations
import numpy as np
import pandas as pd

from src.models import ESResult


def expected_shortfall(
    portfolio_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> ESResult:
    """
    Historical ES: mean of returns worse than the VaR threshold.
    Multi-day: uses the same non-overlapping-window approach as historical VaR.
    """
    r = portfolio_returns.dropna().values

    if horizon_days > 1:
        n_windows = len(r) // horizon_days
        dist = np.array([r[i * horizon_days: (i + 1) * horizon_days].sum()
                         for i in range(n_windows)])
    else:
        dist = r

    var_threshold = np.percentile(dist, (1 - confidence) * 100)
    tail = dist[dist <= var_threshold]
    tail_obs = len(tail)

    if tail_obs == 0:
        es_return = var_threshold
    else:
        es_return = float(tail.mean())

    unstable = tail_obs < 30

    return ESResult(
        amount=abs(es_return * portfolio_value),
        percent=abs(es_return),
        confidence=confidence,
        horizon_days=horizon_days,
        tail_obs=tail_obs,
        unstable=unstable,
    )
