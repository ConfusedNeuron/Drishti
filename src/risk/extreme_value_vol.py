"""Extreme-value (range-based) volatility estimators (FRM Wk7): Parkinson,
Garman-Klass, Rogers-Satchell. Each takes an OHLC frame (columns open/high/low/
close, matching series_io.load_ohlc) and returns a single volatility number
(daily, or annualized x sqrt(252))."""
from __future__ import annotations
import numpy as np
import pandas as pd

_ANN = np.sqrt(252)


def _annualize(daily_var: float, annualize: bool) -> float:
    if not np.isfinite(daily_var):
        return float("nan")
    daily_var = max(float(daily_var), 0.0)   # math guarantees >=0 on clean bars; guards dirty ticks
    daily_vol = np.sqrt(daily_var)
    return float(daily_vol * _ANN) if annualize else float(daily_vol)


def _ready(ohlc: pd.DataFrame, cols: tuple[str, ...]) -> bool:
    if ohlc.empty:
        return False
    missing = [c for c in cols if c not in ohlc.columns]
    if missing:
        raise KeyError(f"OHLC frame missing columns: {missing}")
    return True


def parkinson(ohlc: pd.DataFrame, annualize: bool = False) -> float:
    if not _ready(ohlc, ("high", "low")):
        return float("nan")
    hl = np.log(ohlc["high"] / ohlc["low"])
    var = (1.0 / (4.0 * np.log(2.0))) * (hl ** 2).mean()
    return _annualize(var, annualize)


def garman_klass(ohlc: pd.DataFrame, annualize: bool = False) -> float:
    if not _ready(ohlc, ("high", "low", "close", "open")):
        return float("nan")
    hl = np.log(ohlc["high"] / ohlc["low"])
    co = np.log(ohlc["close"] / ohlc["open"])
    var = (0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2).mean()
    return _annualize(var, annualize)


def rogers_satchell(ohlc: pd.DataFrame, annualize: bool = False) -> float:
    if not _ready(ohlc, ("high", "low", "close", "open")):
        return float("nan")
    ho = np.log(ohlc["high"] / ohlc["open"])
    hc = np.log(ohlc["high"] / ohlc["close"])
    lo = np.log(ohlc["low"] / ohlc["open"])
    lc = np.log(ohlc["low"] / ohlc["close"])
    var = (ho * hc + lo * lc).mean()
    return _annualize(var, annualize)
