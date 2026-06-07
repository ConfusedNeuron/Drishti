"""
Bloomberg parquet cache.

Layout: data/cache/bloomberg/{category}/{ticker_safe}.parquet
Public gap-fill: data/cache/public/{category}/{ticker_safe}.parquet
Bloomberg rows win on date overlap in read_merged().
"""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config import CACHE_DIR, DATA_DIR

PUBLIC_CACHE_DIR = DATA_DIR / "cache" / "public"


def _safe(ticker: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", ticker)


def category(ticker: str) -> str:
    """Route a Bloomberg ticker to its cache subdirectory."""
    t = ticker.upper()
    if "COMDTY" in t:
        return "commodities"
    if "CURNCY" in t:
        return "macro"
    # Macro factors that contain "Index" but are NOT equity indices — check FIRST
    if "GIND" in t or "INVIXN" in t:
        return "macro"
    if "NSE" in t or "NIFTY" in t or "SENSEX" in t or "INDEX" in t:
        return "indices"
    return "equities"


def cache_path(ticker: str) -> Path:
    cat = category(ticker)
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


def read_merged(ticker: str) -> pd.DataFrame | None:
    """Merge Bloomberg cache with public gap-fill. Bloomberg rows win on overlap."""
    bbg = read_cache(ticker)
    pub_path = PUBLIC_CACHE_DIR / category(ticker) / f"{_safe(ticker)}.parquet"
    if not pub_path.exists():
        return bbg
    pub = pd.read_parquet(pub_path)
    if not isinstance(pub.index, pd.DatetimeIndex):
        pub.index = pd.to_datetime(pub.index)
    pub = pub.sort_index()
    if bbg is None:
        return pub
    combined = pd.concat([pub, bbg]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined


def write_cache(ticker: str, df: pd.DataFrame) -> None:
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
    df = read_merged(ticker)
    if df is None:
        return None
    if field not in df.columns:
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
    _, last = get_cached_range(ticker)
    if last is None:
        return None
    from datetime import date as _date
    return (_date.today() - last).days
