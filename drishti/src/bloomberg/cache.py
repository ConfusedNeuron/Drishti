"""
Bloomberg parquet cache.

Layout: data/cache/bloomberg/{category}/{ticker_safe}.parquet
Each file is a DataFrame with DatetimeIndex and one column per field.
Cache is append-only: new date ranges are merged in.
"""
from __future__ import annotations
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config import CACHE_DIR


def _safe(ticker: str) -> str:
    """Convert Bloomberg ticker to a filesystem-safe filename."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", ticker)


def _category(ticker: str) -> str:
    t = ticker.upper()
    if "COMDTY" in t:
        return "commodities"
    if "CURNCY" in t:
        return "macro"
    if "NSE" in t or "NIFTY" in t or "SENSEX" in t:
        return "indices"
    if "GIND" in t or "INVIXN" in t:
        return "macro"
    return "equities"


def cache_path(ticker: str) -> Path:
    cat = _category(ticker)
    path = CACHE_DIR / cat
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{_safe(ticker)}.parquet"


def read_cache(ticker: str) -> pd.DataFrame | None:
    p = cache_path(ticker)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df.sort_index()


def write_cache(ticker: str, df: pd.DataFrame) -> None:
    """Merge new data into existing cache (union of dates)."""
    if df.empty:
        return
    existing = read_cache(ticker)
    if existing is not None:
        df = pd.concat([existing, df]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
    pq.write_table(pa.Table.from_pandas(df), cache_path(ticker))


def get_cached_range(ticker: str) -> tuple[date | None, date | None]:
    df = read_cache(ticker)
    if df is None or df.empty:
        return None, None
    return df.index.min().date(), df.index.max().date()


def get_prices(ticker: str,
               start: date,
               end: date,
               field: str = "PX_LAST") -> pd.Series | None:
    """
    Return cached daily price series for a ticker.
    Returns None if no cache exists or range not covered.
    """
    df = read_cache(ticker)
    if df is None:
        return None
    if field not in df.columns:
        # Try first column
        if df.empty:
            return None
        field = df.columns[0]
    mask = (df.index.date >= start) & (df.index.date <= end)
    series = df.loc[mask, field].dropna()
    if series.empty:
        return None
    return series


def list_cached_tickers() -> list[str]:
    tickers = []
    for p in CACHE_DIR.rglob("*.parquet"):
        tickers.append(p.stem)
    return tickers


def cache_freshness_days(ticker: str) -> int | None:
    """Days since last cached date. None if not cached."""
    _, last = get_cached_range(ticker)
    if last is None:
        return None
    return (date.today() - last).days
