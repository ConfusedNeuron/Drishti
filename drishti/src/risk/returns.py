"""
Return matrix builder.

Loads adjusted close price series from Bloomberg cache for each holding,
aligns on common Indian trading dates, computes simple daily returns.
"""
from __future__ import annotations
from datetime import date

import numpy as np
import pandas as pd

from src.bloomberg.cache import get_prices
from src.models import PortfolioSnapshot


def build_return_matrix(
    snapshot: PortfolioSnapshot,
    start: date,
    end: date,
    field: str = "PX_ADJ_CLOSE",
) -> tuple[pd.DataFrame, list[str]]:
    """
    Returns:
        returns_df  — DataFrame of daily simple returns, DatetimeIndex, columns = symbols
        missing     — symbols with no cached price data
    """
    prices = {}
    missing = []

    for h in snapshot.modeled_holdings:
        # Try adjusted close first, fall back to PX_LAST
        series = get_prices(h.bbg_ticker, start, end, field)
        if series is None:
            series = get_prices(h.bbg_ticker, start, end, "PX_LAST")
        if series is None or len(series) < 60:
            missing.append(h.symbol)
            continue
        prices[h.symbol] = series

    if not prices:
        return pd.DataFrame(), missing

    price_df = pd.DataFrame(prices)
    price_df.index = pd.to_datetime(price_df.index)
    price_df = price_df.sort_index().dropna(how="all")

    # Align: forward-fill small gaps (max 3 trading days), then drop any remaining NaN rows
    price_df = price_df.ffill(limit=3).dropna()

    returns_df = price_df.pct_change().dropna()
    return returns_df, missing


def portfolio_returns(returns_df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted portfolio return series."""
    common = [s for s in weights if s in returns_df.columns]
    if not common:
        raise ValueError("No overlap between weights and return matrix columns")
    w = pd.Series(weights)[common]
    w = w / w.sum()  # renormalize in case of missing symbols
    port = returns_df[common].dot(w)
    port.name = "portfolio"
    return port


def covariance_matrix(returns_df: pd.DataFrame, annualize: bool = False) -> np.ndarray:
    cov = returns_df.cov().values
    if annualize:
        cov = cov * 252
    return cov


def load_factor_series(
    factor_ids: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Load commodity/macro factor return series from cache.
    factor_ids: keys from config.ALL_FACTOR_TICKERS, e.g. ["brent", "gold", "usdinr"]
    Returns DataFrame of daily returns aligned to common dates.
    """
    from src.config import ALL_FACTOR_TICKERS

    series_dict = {}
    for fid in factor_ids:
        ticker = ALL_FACTOR_TICKERS.get(fid)
        if ticker is None:
            continue
        s = get_prices(ticker, start, end, "PX_LAST")
        if s is not None and len(s) > 10:
            series_dict[fid] = s

    if not series_dict:
        return pd.DataFrame()

    df = pd.DataFrame(series_dict)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill(limit=3).dropna()

    # For yield-type series (gsec10y), use level changes not pct returns
    if "gsec10y" in df.columns:
        df["gsec10y"] = df["gsec10y"].diff()

    ret = df.pct_change().dropna()
    if "gsec10y" in ret.columns:
        # Overwrite with raw change (already computed above)
        ret["gsec10y"] = df["gsec10y"].reindex(ret.index)

    return ret


def load_sector_returns(
    sector_ids: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    from src.config import SECTOR_TICKERS
    from src.bloomberg.cache import get_prices as gp

    series_dict = {}
    for sid in sector_ids:
        ticker = SECTOR_TICKERS.get(sid)
        if ticker is None:
            continue
        s = gp(ticker, start, end, "PX_LAST")
        if s is not None and len(s) > 10:
            series_dict[sid] = s

    if not series_dict:
        return pd.DataFrame()

    df = pd.DataFrame(series_dict)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill(limit=3).dropna()
    return df.pct_change().dropna()
