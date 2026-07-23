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


def filter_min_history(price_df: pd.DataFrame, min_days: int) -> pd.DataFrame:
    """Drop columns with fewer than min_days non-NaN observations.
    Prevents one young listing from truncating the whole aligned matrix."""
    keep = [c for c in price_df.columns if price_df[c].dropna().shape[0] >= min_days]
    return price_df[keep]


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
    from src.config import MIN_HISTORY_DAYS

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

    # Drop young listings that don't meet minimum history threshold
    dropped_young = [c for c in price_df.columns
                     if c not in filter_min_history(price_df, MIN_HISTORY_DAYS).columns]
    missing.extend(dropped_young)
    price_df = filter_min_history(price_df, MIN_HISTORY_DAYS)
    if price_df.empty:
        return pd.DataFrame(), missing

    # Align: forward-fill small gaps (max 3 trading days), then drop any remaining NaN rows
    price_df = price_df.ffill(limit=3).dropna()

    returns_df = price_df.pct_change(fill_method=None).dropna()
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

    ret = df.pct_change(fill_method=None)
    if "gsec10y" in df.columns:
        # 10y G-sec is a yield: use level changes (bps move), not percentage returns.
        ret["gsec10y"] = df["gsec10y"].diff()
    return ret.dropna()


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
    return df.pct_change(fill_method=None).dropna()


def prepare_portfolio_inputs(
    snap: PortfolioSnapshot, start: date, end: date
) -> tuple[pd.Series, np.ndarray, list[str], pd.DataFrame, list[str]]:
    """Build the aligned inputs every VaR/ES consumer needs from a snapshot.

    Returns (port_ret, w_arr, common, cov, missing). Raises ValueError when
    the cache has no data or no symbols overlap the portfolio.
    """
    returns_df, missing = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise ValueError(f"No cached price data. Run data pull first. Missing: {missing}")
    common = [s for s in snap.weights if s in returns_df.columns]
    if not common:
        raise ValueError("No overlap between portfolio symbols and cached data.")
    w = {s: snap.weights[s] for s in common}
    total = sum(w.values())
    w_norm = {s: v / total for s, v in w.items()}
    port_ret = portfolio_returns(returns_df, w_norm)
    w_arr = np.array([w_norm[s] for s in common])
    cov = covariance_matrix(returns_df[common])
    return port_ret, w_arr, common, cov, missing
