"""
Pull public data (yfinance + FRED) to gap-fill the Bloomberg cache.

For each Bloomberg ticker, reads the last cached date and fetches only
new rows since then. Appends to data/cache/public/{category}/{ticker}.parquet.
Bloomberg parquets are never modified.

Usage:
    python scripts/pull_public_data.py [--dry-run] [--ticker "TICKER"]
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MAPPINGS  = ROOT / "data" / "mappings" / "yahoo_tickers.json"
PUBLIC_DIR = ROOT / "data" / "cache" / "public"
MIN_GAP_DAYS = 3
RATE_LIMIT_SEC = 0.5


def _category(ticker: str) -> str:
    t = ticker.upper()
    if "COMDTY" in t: return "commodities"
    if "CURNCY" in t: return "macro"
    if "NSE" in t or "NIFTY" in t or "SENSEX" in t: return "indices"
    if "GIND" in t or "INVIXN" in t: return "macro"
    return "equities"


def _safe(ticker: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_-]", "_", ticker)


def _get_last_date(bbg_ticker: str) -> date | None:
    try:
        from src.bloomberg.cache import get_cached_range
        _, last = get_cached_range(bbg_ticker)
        return last
    except Exception:
        return None


def _pub_path(bbg_ticker: str) -> Path:
    cat = _category(bbg_ticker)
    p = PUBLIC_DIR / cat
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{_safe(bbg_ticker)}.parquet"


def _append_parquet(path: Path, df) -> None:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    if df.empty:
        return
    if path.exists():
        existing = pd.read_parquet(path)
        if not isinstance(existing.index, pd.DatetimeIndex):
            existing.index = pd.to_datetime(existing.index)
        df = pd.concat([existing, df]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
    pq.write_table(pa.Table.from_pandas(df), path)


def _fetch_yfinance(yahoo_ticker: str, start: date, end: date):
    import pandas as pd
    import yfinance as yf
    df = yf.download(yahoo_ticker, start=str(start), end=str(end),
                     auto_adjust=True, progress=False, show_errors=False)
    if df is None or df.empty:
        return None
    if hasattr(df.columns, 'levels'):
        df.columns = df.columns.get_level_values(0)
    close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
    result = pd.DataFrame({"PX_LAST": close})
    result.index = pd.to_datetime(result.index)
    result.index.name = "date"
    return result.dropna()


def _fetch_fred(series_id: str, start: date, end: date):
    import os
    import pandas as pd
    api_key = os.getenv("FRED_API_KEY", "")
    if not api_key:
        print(f"    SKIP FRED:{series_id} — FRED_API_KEY not set")
        return None
    from fredapi import Fred
    fred = Fred(api_key=api_key)
    s = fred.get_series(series_id, observation_start=str(start), observation_end=str(end))
    if s is None or s.empty:
        return None
    result = pd.DataFrame({"PX_LAST": s})
    result.index = pd.to_datetime(result.index)
    result.index.name = "date"
    return result.dropna()


def pull_ticker(bbg_ticker: str, yahoo_value: str, dry_run: bool = False) -> int:
    last = _get_last_date(bbg_ticker)
    today = date.today()
    if last is None:
        start = date(2018, 1, 1)
    elif (today - last).days <= MIN_GAP_DAYS:
        print(f"  SKIP {bbg_ticker} — only {(today - last).days}d stale")
        return 0
    else:
        start = last + timedelta(days=1)

    print(f"  FETCH {bbg_ticker} via {yahoo_value}  [{start} → {today}]")
    if dry_run:
        return 0

    if yahoo_value.startswith("FRED:"):
        df = _fetch_fred(yahoo_value[5:], start, today)
    else:
        try:
            df = _fetch_yfinance(yahoo_value, start, today)
        except Exception as e:
            print(f"    ERROR: {e}")
            return 0

    if df is None or df.empty:
        print(f"    no new rows")
        return 0

    _append_parquet(_pub_path(bbg_ticker), df)
    print(f"    wrote {len(df)} rows")
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull public data gap-fill for Drishti")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be fetched without writing")
    parser.add_argument("--ticker", metavar="BLOOMBERG_TICKER",
                        help="Pull only this Bloomberg ticker")
    args = parser.parse_args()

    mapping = json.loads(MAPPINGS.read_text())
    pairs: list[tuple[str, str]] = []
    for category in ("equities", "indices", "commodities", "macro"):
        for bbg, yahoo in mapping.get(category, {}).items():
            pairs.append((bbg, yahoo))

    if args.ticker:
        pairs = [(b, y) for b, y in pairs if b == args.ticker]
        if not pairs:
            print(f"Ticker '{args.ticker}' not found in yahoo_tickers.json")
            return

    total = 0
    for bbg_ticker, yahoo_ticker in pairs:
        total += pull_ticker(bbg_ticker, yahoo_ticker, dry_run=args.dry_run)
        time.sleep(RATE_LIMIT_SEC)

    print(f"\nDone. Total new rows written: {total}")


if __name__ == "__main__":
    main()
