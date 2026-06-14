"""Load v2 index / commodity / macro / OHLC price frames from the parquet cache.
Bloomberg tickers use full form ("NIFTY Index"); filenames replace spaces with _."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from src.config import DATA_DIR

V2 = DATA_DIR / "cache" / "bloomberg_v2"


def _fname(ticker: str) -> str:
    return ticker.replace(" ", "_") + ".parquet"


def _load_close(tickers: list[str], subdir: str) -> pd.DataFrame:
    out = {}
    for t in tickers:
        p = V2 / subdir / _fname(t)
        if p.exists():
            df = pd.read_parquet(p)
            if "PX_LAST" in df.columns:        # guard for parity with load_v2_returns
                out[t] = df["PX_LAST"]
    if not out:
        return pd.DataFrame()
    px = pd.DataFrame(out)
    px.index = pd.to_datetime(px.index)
    return px.sort_index()


def load_index_prices(tickers: list[str]) -> pd.DataFrame:
    return _load_close(tickers, "indices")


def load_commodity_prices(tickers: list[str]) -> pd.DataFrame:
    return _load_close(tickers, "commodities")


def load_macro_prices(tickers: list[str]) -> pd.DataFrame:
    return _load_close(tickers, "macro")


def load_ohlc(ticker: str, subdir: str) -> pd.DataFrame:
    """Frame with columns open/high/low/close (lowercase) for one ticker.
    Empty frame if the ohlc parquet is absent (pre-pull graceful degradation)."""
    p = V2 / "ohlc" / subdir / _fname(ticker)
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p).rename(columns={
        "PX_OPEN": "open", "PX_HIGH": "high", "PX_LOW": "low", "PX_LAST": "close"})
    df.index = pd.to_datetime(df.index)
    return df[[c for c in ["open", "high", "low", "close"] if c in df.columns]].sort_index()
