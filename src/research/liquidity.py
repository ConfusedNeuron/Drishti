"""Amihud (2002) illiquidity ratio (FRM Wk9): average of |return| divided by
traded value (price * volume). Higher = more price impact per unit traded.
`volume` must be share count (e.g. Bloomberg PX_VOLUME); `returns` daily and
index-aligned to price/volume. scale=1e6 is Amihud's standard display convention."""
from __future__ import annotations
import numpy as np
import pandas as pd


def amihud(returns: pd.Series, price: pd.Series, volume: pd.Series,
           scale: float = 1e6) -> float:
    j = pd.concat([returns.abs(), price, volume], axis=1).dropna()
    j.columns = ["absret", "px", "vol"]
    traded_value = j["px"] * j["vol"]
    j = j[traded_value > 0]                  # avoid divide-by-zero on no-trade days
    illiq = (j["absret"] / (j["px"] * j["vol"])).mean()
    return float(illiq * scale)
