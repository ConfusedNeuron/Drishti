"""
pull_drishti_data.py -- Bloomberg BLPAPI data pull for Drishti
==============================================================

Run this script on the Bloomberg Terminal machine at FRTL.
Bloomberg Terminal must be running and logged in before you start.

    cd C:\\Users\\User\\Pranav\\drishti
    .venv\\Scripts\\activate
    python scripts/pull_drishti_data.py

Output written to data/cache/bloomberg/ (one parquet file per ticker):

    data/cache/bloomberg/
      equities/         RELIANCE_IN_Equity.parquet   PX_LAST, PX_ADJ_CLOSE
      indices/          NSEOILGS_Index.parquet        PX_LAST
      commodities/      CO1_Comdty.parquet            PX_LAST
      macro/            USDINR_Curncy.parquet         PX_LAST

Passes
------
--validate          Test all fields on 5 tickers before the full pull. Run this
                    first if you are unsure which fields work on this terminal.
--skip-equities     Skip the equity pull (~45-60 min). Pull indices/commodities/
                    macro first (fast, <5 min), verify, then rerun without this
                    flag to pull equities.
--output-dir PATH   Override cache output directory (default: data/cache/bloomberg).
--start-date DATE   Override pull start date (YYYYMMDD, default: 20180101).

Resumability
------------
Each ticker is saved to its own parquet file immediately after pull.
If the script is interrupted, already-saved tickers are skipped on rerun.
A progress bar shows how many remain.

Bloomberg data policy
---------------------
Data pulled here is for academic research only (FRTL, IIM Calcutta).
The data/ directory is gitignored. Do not commit parquet files to GitHub.
Cite "Bloomberg Terminal, FRTL, IIM Calcutta" in all research outputs.

Known FRTL field issues (from BLOOMBERG_TERMINAL_GUIDE.md)
-----------------------------------------------------------
- IS_* fields (IS_NET_INC, IS_EPS_*) return 100% null -- use CF_* / NET_INCOME instead
- RETURN_ON_EQY returns null -- use RETURN_COM_EQY
- INDX_MEMBERS / INDX_MWEIGHT_HIST return 0 rows (entitlement issue) -- not used here
- TRAIL_12M_* fields null in HistoricalDataRequest -- avoid
- WARN blpapi_subscriptionmanager.cpp: harmless, ignore
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

# blpapi is only available on the Bloomberg Terminal machine.
# On a dev machine without it, imports succeed but connect() will bail cleanly.
try:
    import blpapi  # type: ignore
    _HAS_BLPAPI = True
except ImportError:
    blpapi = None
    _HAS_BLPAPI = False


# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

# Resolved against this file's location so the script works from any cwd.
_SCRIPT_DIR  = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
_DEFAULT_CACHE_DIR = _PROJECT_DIR / "data" / "cache" / "bloomberg"

# Date range: 2018 to today gives 7 years, covers COVID-2020 and 2022 drawdown.
# These are the two stress events Drishti validates HMM regime detection against.
PULL_START = "20180101"
PULL_END   = date.today().strftime("%Y%m%d")

# Bloomberg session defaults (Bloomberg Terminal runs a local server on this port)
BBG_HOST = "localhost"
BBG_PORT  = 8194

# Chunk size and sleep between chunks -- 100/0.25 s is stable at FRTL
CHUNK_SIZE    = 100
SLEEP_SECONDS = 0.25


# ── Ticker lists ──────────────────────────────────────────────────────────────

# NSE sector indices -- primary DCC-GARCH / Diebold-Yilmaz spillover targets.
# Banks excluded: commodity→CPI→RBI repo→banks is a mediated channel captured
# via the G-Sec yield factor, not as a direct sector target.
SECTOR_TICKERS: dict[str, str] = {
    "NSEOILGS Index": "energy",
    "NSEMETAL Index":  "metals",
    "NSEFMCG Index":   "fmcg",
    "NSEIT Index":     "it",
    "NSEBANK Index":   "banks",     # pulled for completeness; excluded from DY targets
    "NSEAUTO Index":   "auto",
    "NSEPHRM Index":   "pharma",
}

# Broad market benchmarks
BENCHMARK_TICKERS: dict[str, str] = {
    "NIFTY Index":  "nifty50",
    "SENSEX Index": "sensex",
}

# Front-month continuous commodity futures.
# CO1 = Brent, CL1 = WTI, GC1 = Gold, HG1 = Copper, NG1 = Natural Gas.
# Roll bias is documented but not adjusted -- small for daily return analysis.
COMMODITY_TICKERS: dict[str, str] = {
    "CO1 Comdty": "brent",
    "CL1 Comdty": "wti",
    "GC1 Comdty": "gold",
    "HG1 Comdty": "copper",
    "NG1 Comdty": "natgas",
}

# Macro factor series
MACRO_TICKERS: dict[str, str] = {
    "USDINR Curncy":  "usdinr",
    "GIND10YR Index": "gsec10y",    # India 10Y G-Sec yield -- use as a level, diff for returns
    "INVIXN Index":   "indiavix",   # India VIX -- HMM feature + regime indicator
}

# NIFTY 50 equities for the sample portfolio and cross-sectional research.
# Ticker format: "{NSE_SYMBOL} IN Equity" -- confirmed via Bloomberg FRTL guide.
# A handful of symbols differ from their NSE display name (noted inline).
EQUITY_TICKERS: list[str] = [
    "RELIANCE IN Equity",
    "TCS IN Equity",
    "HDFCBANK IN Equity",
    "INFY IN Equity",
    "ICICIBANK IN Equity",
    "HINDUNILVR IN Equity",
    "ITC IN Equity",
    "SBIN IN Equity",
    "BAJFINANCE IN Equity",
    "KOTAKBANK IN Equity",
    "LT IN Equity",
    "ASIANPAINT IN Equity",
    "TITAN IN Equity",
    "NESTLEIND IN Equity",
    "MARUTI IN Equity",
    "ONGC IN Equity",
    "NTPC IN Equity",
    "POWERGRID IN Equity",
    "WIPRO IN Equity",
    "HCLTECH IN Equity",
    "BJAUT IN Equity",          # NSE: BAJAJ-AUTO
    "TATAMOTORS IN Equity",
    "TATASTEEL IN Equity",
    "HINDALCO IN Equity",
    "COAL IN Equity",           # NSE: COALINDIA
    "JSTL IN Equity",           # NSE: JSWSTEEL
    "CIPLA IN Equity",
    "DRRD IN Equity",           # NSE: DRREDDY
    "SUNP IN Equity",           # NSE: SUNPHARMA
    "ADE IN Equity",            # NSE: ADANIENT
    "ADSEZ IN Equity",          # NSE: ADANIPORTS
    "UTCEM IN Equity",          # NSE: ULTRACEMCO
    "GRASIM IN Equity",
    "BRIT IN Equity",           # NSE: BRITANNIA
    "EIM IN Equity",            # NSE: EICHERMOT
    "HMCL IN Equity",           # NSE: HEROMOTOCO
    "DIVI IN Equity",           # NSE: DIVISLAB
    "APHS IN Equity",           # NSE: APOLLOHOSP
    "BHARTI IN Equity",         # NSE: BHARTIARTL
    "BPCL IN Equity",
    "IOCL IN Equity",           # NSE: IOC
    "MM IN Equity",             # NSE: M&M
    "TECHM IN Equity",
    "IIB IN Equity",            # NSE: INDUSINDBK
    "BJFIN IN Equity",          # NSE: BAJAJFINSV
    "UPLL IN Equity",           # NSE: UPL
]

# Fields for equity historical data requests.
# PX_ADJ_CLOSE: adjusted for splits and dividends -- use for returns.
# PX_LAST: unadjusted close -- kept as fallback.
# Confirmed working on FRTL (see BLOOMBERG_TERMINAL_GUIDE.md).
EQUITY_FIELDS = ["PX_ADJ_CLOSE", "PX_LAST"]

# All non-equity series use PX_LAST (they are index/futures levels, not equity prices).
INDEX_FIELDS = ["PX_LAST"]

# Validation tickers -- 5 stable large-caps used to test fields before a full pull.
VALIDATE_TICKERS = [
    "RELIANCE IN Equity",
    "TCS IN Equity",
    "HDFCBANK IN Equity",
    "INFY IN Equity",
    "ONGC IN Equity",
]


# ──────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ──────────────────────────────────────────────────────────────────────────────

def ticker_to_filename(ticker: str) -> str:
    """
    Convert a Bloomberg ticker to a filesystem-safe filename (no extension).

    Example: "RELIANCE IN Equity" -> "RELIANCE_IN_Equity"
             "CO1 Comdty"         -> "CO1_Comdty"
    """
    return re.sub(r"[^A-Za-z0-9_-]", "_", ticker)


def cache_path_for(ticker: str, cache_dir: Path) -> Path:
    """
    Return the parquet path for a ticker, matching src/bloomberg/cache.py layout.

    Layout: {cache_dir}/{category}/{ticker_safe}.parquet
    """
    t = ticker.upper()
    if "COMDTY" in t:
        cat = "commodities"
    elif "CURNCY" in t:
        cat = "macro"
    elif any(x in t for x in ("INDEX", "NIFTY", "SENSEX", "NSE", "GIND", "INVIXN")):
        cat = "indices"
    else:
        cat = "equities"

    subdir = cache_dir / cat
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir / f"{ticker_to_filename(ticker)}.parquet"


def chunks(lst: list, size: int) -> list[list]:
    return [lst[i: i + size] for i in range(0, len(lst), size)]


def element_to_python(element: Any) -> Any:
    """Convert a Bloomberg element scalar to a plain Python value."""
    if element.isNull():
        return None
    for getter in ("getValueAsFloat", "getValueAsInteger",
                   "getValueAsDatetime", "getValueAsString"):
        try:
            return getattr(element, getter)()
        except Exception:
            pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# SESSION
# ──────────────────────────────────────────────────────────────────────────────

def open_session(host: str = BBG_HOST, port: int = BBG_PORT) -> Any:
    """Connect to the Bloomberg Terminal's local BLPAPI server."""
    if not _HAS_BLPAPI:
        raise SystemExit(
            "blpapi not installed.\n"
            "Install it on the Bloomberg Terminal machine with:\n"
            "  python -m pip install --index-url "
            "https://blpapi.bloomberg.com/repository/releases/python/simple/ blpapi\n"
            "Do not use bare pip -- it installs to system Python, not the venv."
        )

    opts = blpapi.SessionOptions()
    opts.setServerHost(host)
    opts.setServerPort(port)

    session = blpapi.Session(opts)
    if not session.start():
        raise RuntimeError(
            "Bloomberg session failed to start.\n"
            "Make sure the Bloomberg Terminal is running and you are logged in."
        )
    if not session.openService("//blp/refdata"):
        raise RuntimeError("Failed to open //blp/refdata service.")

    print("Bloomberg session connected.")
    return session


# ──────────────────────────────────────────────────────────────────────────────
# BLOOMBERG REQUESTS
# ──────────────────────────────────────────────────────────────────────────────

def _parse_bdh_response(session: Any, fields: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """
    Consume all BDH response events from the session and return a DataFrame.

    Returns
    -------
    df     : rows = (date, ticker, field_values...)
    errors : list of tickers Bloomberg flagged as invalid / no-data
    """
    rows: list[dict] = []
    errors: list[str] = []

    while True:
        ev = session.nextEvent(500)
        for msg in ev:
            if not msg.hasElement("securityData"):
                continue

            sec = msg.getElement("securityData")
            ticker = sec.getElementAsString("security") if sec.hasElement("security") else "unknown"

            if sec.hasElement("securityError"):
                errors.append(ticker)
                continue

            field_data_arr = sec.getElement("fieldData")
            for i in range(field_data_arr.numValues()):
                pt = field_data_arr.getValueAsElement(i)
                row: dict = {"ticker": ticker}
                try:
                    row["date"] = pt.getElementAsDatetime("date")
                except Exception:
                    continue
                for field in fields:
                    row[field] = (
                        element_to_python(pt.getElement(field))
                        if pt.hasElement(field) else None
                    )
                rows.append(row)

        if ev.eventType() == blpapi.Event.RESPONSE:
            break

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
    return df, errors


def bdh(
    session: Any,
    tickers: list[str],
    fields: list[str],
    start_date: str,
    end_date: str,
    periodicity: str = "DAILY",
    adj_split: bool = True,
    adj_normal: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Historical data request (BDH).

    Sends one HistoricalDataRequest for all tickers in the list.
    Keep chunks to <=100 tickers to avoid timeouts.

    Parameters
    ----------
    adj_split  : True = adjust for stock splits
    adj_normal : True = adjust for dividends (normal adjustments)
    """
    svc = session.getService("//blp/refdata")
    req = svc.createRequest("HistoricalDataRequest")

    for ticker in tickers:
        req.getElement("securities").appendValue(ticker)
    for field in fields:
        req.getElement("fields").appendValue(field)

    req.set("startDate", start_date)
    req.set("endDate",   end_date)
    req.set("periodicitySelection", periodicity)
    req.set("adjustmentSplit",   adj_split)
    req.set("adjustmentNormal",  adj_normal)   # dividend adjustment

    session.sendRequest(req)
    return _parse_bdh_response(session, fields)


def bdp(session: Any, tickers: list[str], fields: list[str]) -> dict[str, dict]:
    """
    Reference data request (BDP).

    Used for ticker validation: send all tickers, ask for SECURITY_NAME,
    Bloomberg returns securityError for invalid/unknown tickers.
    """
    svc = session.getService("//blp/refdata")
    req = svc.createRequest("ReferenceDataRequest")

    for ticker in tickers:
        req.getElement("securities").appendValue(ticker)
    for field in fields:
        req.getElement("fields").appendValue(field)

    session.sendRequest(req)

    result: dict[str, dict] = {}
    while True:
        ev = session.nextEvent(500)
        for msg in ev:
            if not msg.hasElement("securityData"):
                continue
            arr = msg.getElement("securityData")
            for i in range(arr.numValues()):
                sec = arr.getValueAsElement(i)
                ticker = sec.getElementAsString("security") if sec.hasElement("security") else ""
                if sec.hasElement("securityError"):
                    result[ticker] = {"valid": False}
                    continue
                fd = sec.getElement("fieldData")
                result[ticker] = {"valid": True}
                for field in fields:
                    try:
                        result[ticker][field] = fd.getElement(field).getValueAsString()
                    except Exception:
                        result[ticker][field] = None
        if ev.eventType() == blpapi.Event.RESPONSE:
            break

    return result


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATE
# ──────────────────────────────────────────────────────────────────────────────

def validate_tickers(session: Any, tickers: list[str]) -> tuple[list[str], list[str]]:
    """
    Send all tickers through BDP SECURITY_NAME.
    Returns (valid_tickers, invalid_tickers).
    Expect ~2% invalid for a large historical universe.
    """
    print(f"\nValidating {len(tickers)} tickers via BDP SECURITY_NAME ...")
    ref = bdp(session, tickers, ["SECURITY_NAME"])

    valid   = [t for t in tickers if ref.get(t, {}).get("valid")]
    invalid = [t for t in tickers if not ref.get(t, {}).get("valid")]

    print(f"  Valid: {len(valid)}  |  Invalid: {len(invalid)}")
    if invalid:
        print(f"  Invalid tickers: {invalid}")
    return valid, invalid


def validate_fields(
    session: Any,
    tickers: list[str],
    fields: list[str],
    start_date: str = "20200101",
    end_date: str   = "20231231",
    periodicity: str = "DAILY",
) -> None:
    """
    Pull 4 years of data for a small set of tickers and report which fields
    have non-null data. Run this before a full pull if unsure which fields
    work on this terminal.

    Bloomberg may accept a field name without error but return 100% null
    (a known FRTL entitlement issue for IS_* and TRAIL_12M_* fields).
    """
    print(f"\nField validation: {fields}")
    print(f"  Tickers: {tickers}")
    print(f"  Period : {start_date} → {end_date} ({periodicity})")

    df, errors = bdh(session, tickers, fields, start_date, end_date, periodicity)

    if errors:
        print(f"  Ticker errors: {errors}")

    print(f"\n  {'Field':<30}  {'Non-null':>10}  {'Status'}")
    print(f"  {'─'*30}  {'─'*10}  {'─'*15}")

    if df.empty:
        print("  No data returned for any field.")
        return

    for field in fields:
        if field in df.columns:
            n = int(df[field].notna().sum())
            status = "✓  HAS DATA" if n > 0 else "✗  ALL NULL"
        else:
            n = 0
            status = "✗  NOT IN RESPONSE"
        print(f"  {field:<30}  {n:>10,}  {status}")


# ──────────────────────────────────────────────────────────────────────────────
# CACHE READ / WRITE
# ──────────────────────────────────────────────────────────────────────────────

def read_cached(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df.sort_index()


def write_to_cache(path: Path, new_df: pd.DataFrame) -> None:
    """
    Merge new_df with any existing parquet at path (union of dates),
    then overwrite. This lets the pull be resumed: re-running extends
    the cache to the latest date rather than discarding old data.
    """
    existing = read_cached(path)
    if existing is not None and not existing.empty:
        combined = pd.concat([existing, new_df]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
    else:
        combined = new_df.sort_index()

    combined.to_parquet(path)


# ──────────────────────────────────────────────────────────────────────────────
# PULL FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def pull_group(
    session: Any,
    ticker_map: dict[str, str],
    fields: list[str],
    start_date: str,
    end_date: str,
    cache_dir: Path,
    label: str,
    skip_existing: bool = True,
) -> list[str]:
    """
    Pull a group of tickers (indices, commodities, or macro) one at a time.

    For small groups (<20 tickers) we pull one ticker per request to get
    a clean per-ticker parquet file. For large groups (equities) use
    pull_equities() which chunks 100 at a time.

    Returns list of tickers that failed.
    """
    all_errors: list[str] = []

    tickers = list(ticker_map.keys())
    desc    = f"Pulling {label}"

    for ticker in tqdm(tickers, desc=desc, unit="ticker"):
        path = cache_path_for(ticker, cache_dir)

        if skip_existing and path.exists():
            tqdm.write(f"  [cached]  {ticker}")
            continue

        try:
            df, errors = bdh(session, [ticker], fields, start_date, end_date)
        except Exception as exc:
            tqdm.write(f"  [error]   {ticker}: {exc}")
            all_errors.append(ticker)
            time.sleep(SLEEP_SECONDS)
            continue

        if errors:
            tqdm.write(f"  [invalid] {ticker}")
            all_errors.extend(errors)
        elif df.empty:
            tqdm.write(f"  [no data] {ticker}")
        else:
            # Drop the ticker column if present; keep only field columns
            if "ticker" in df.columns:
                df = df.drop(columns=["ticker"])
            write_to_cache(path, df)
            n_rows = len(df)
            tqdm.write(f"  [ok]      {ticker:<35} {n_rows:>5} rows → {path.name}")

        time.sleep(SLEEP_SECONDS)

    return all_errors


def pull_equities(
    session: Any,
    tickers: list[str],
    fields: list[str],
    start_date: str,
    end_date: str,
    cache_dir: Path,
    skip_existing: bool = True,
) -> list[str]:
    """
    Pull equity price series, 100 tickers per request.

    Each ticker gets its own parquet file immediately after the chunk completes.
    If interrupted, already-saved tickers are skipped on rerun.

    Equities take ~45-60 min for a full NIFTY 50 pull. Run with --skip-equities
    first to verify all other data, then rerun without it for the equity pull.
    """
    # Filter out tickers already cached
    remaining = [t for t in tickers
                 if not skip_existing or not cache_path_for(t, cache_dir).exists()]
    n_skipped  = len(tickers) - len(remaining)

    if n_skipped:
        print(f"  Skipping {n_skipped} already-cached equity tickers.")

    if not remaining:
        print("  All equity tickers already cached.")
        return []

    all_errors: list[str] = []
    ticker_chunks = chunks(remaining, CHUNK_SIZE)

    print(f"  Pulling {len(remaining)} equities in {len(ticker_chunks)} chunks "
          f"({CHUNK_SIZE} tickers/chunk, {SLEEP_SECONDS}s sleep) ...")

    for chunk in tqdm(ticker_chunks, desc="Equity chunks", unit="chunk"):
        try:
            df, errors = bdh(session, chunk, fields, start_date, end_date)
        except Exception as exc:
            tqdm.write(f"  [chunk error] {exc}")
            all_errors.extend(chunk)
            time.sleep(SLEEP_SECONDS)
            continue

        all_errors.extend(errors)

        if not df.empty and "ticker" in df.columns:
            # Split the multi-ticker response into one file per ticker
            for ticker, ticker_df in df.groupby("ticker"):
                path     = cache_path_for(ticker, cache_dir)
                clean_df = ticker_df.drop(columns=["ticker"])
                write_to_cache(path, clean_df)

        time.sleep(SLEEP_SECONDS)

    return all_errors


# ──────────────────────────────────────────────────────────────────────────────
# VERIFY
# ──────────────────────────────────────────────────────────────────────────────

def verify_outputs(cache_dir: Path) -> None:
    """Print a summary of what was written to the cache directory."""
    categories = ["equities", "indices", "commodities", "macro"]

    print("\n── Output verification ─────────────────────────────────────────────")
    total_files = 0

    for cat in categories:
        subdir = cache_dir / cat
        if not subdir.exists():
            print(f"  {cat:<15}  (directory not created)")
            continue

        files = sorted(subdir.glob("*.parquet"))
        n     = len(files)
        total_files += n

        if n == 0:
            print(f"  {cat:<15}  0 files  ⚠️  empty")
            continue

        # Show date range and row count across all files in this category
        min_date, max_date, total_rows = None, None, 0
        for f in files:
            try:
                df = pd.read_parquet(f)
                if df.empty:
                    continue
                idx = pd.to_datetime(df.index)
                total_rows += len(df)
                f_min, f_max = idx.min().date(), idx.max().date()
                if min_date is None or f_min < min_date:
                    min_date = f_min
                if max_date is None or f_max > max_date:
                    max_date = f_max
            except Exception:
                pass

        size_mb = sum(f.stat().st_size for f in files) / 1_048_576
        print(f"  {cat:<15}  {n:>3} files  "
              f"{str(min_date):<12} → {str(max_date):<12}  "
              f"{total_rows:>8,} rows  {size_mb:>6.1f} MB")

    print(f"\n  Total: {total_files} parquet files in {cache_dir}")
    print("\n  Ready to use with Drishti dashboard.")
    print("  Copy data/cache/ to your laptop before the demo.")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull Bloomberg data for Drishti (run on FRTL Bloomberg Terminal machine).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "Test all fields on 5 tickers and print which ones return data. "
            "Run this first if unsure about field availability on this terminal. "
            "No files are written."
        ),
    )
    parser.add_argument(
        "--skip-equities",
        action="store_true",
        help=(
            "Skip the equity price pull (~45-60 min for NIFTY 50). "
            "Useful for a quick first run to verify indices, commodities, and macro."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_CACHE_DIR,
        help=f"Cache output directory. Default: {_DEFAULT_CACHE_DIR}",
    )
    parser.add_argument(
        "--start-date",
        default=PULL_START,
        help=f"Pull start date in YYYYMMDD format. Default: {PULL_START}",
    )
    parser.add_argument(
        "--end-date",
        default=PULL_END,
        help=f"Pull end date in YYYYMMDD format. Default: today ({PULL_END})",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-pull all tickers even if already cached. Default: skip cached tickers.",
    )

    args = parser.parse_args()

    cache_dir   = args.output_dir.resolve()
    start_date  = args.start_date
    end_date    = args.end_date
    skip_exist  = not args.no_resume

    print("──────────────────────────────────────────────────────────────────")
    print("  Drishti Bloomberg Data Pull")
    print("──────────────────────────────────────────────────────────────────")
    print(f"  Date range  : {start_date} → {end_date}")
    print(f"  Output dir  : {cache_dir}")
    print(f"  Resume mode : {'yes (skip cached)' if skip_exist else 'no (re-pull all)'}")
    print(f"  Skip equity : {args.skip_equities}")
    print()

    # ── Connect ──────────────────────────────────────────────────────────────
    session = open_session()

    try:
        # ── Validate mode: test fields, print report, exit ────────────────
        if args.validate:
            print("\n── Field validation mode ───────────────────────────────────────")
            validate_fields(
                session,
                tickers=VALIDATE_TICKERS,
                fields=EQUITY_FIELDS,
                start_date="20200101",
                end_date="20231231",
            )
            validate_fields(
                session,
                tickers=list(COMMODITY_TICKERS.keys()),
                fields=INDEX_FIELDS,
                start_date="20200101",
                end_date="20231231",
            )
            validate_fields(
                session,
                tickers=list(MACRO_TICKERS.keys()),
                fields=INDEX_FIELDS,
                start_date="20200101",
                end_date="20231231",
            )
            print("\nValidation complete. Re-run without --validate to pull data.")
            return

        all_errors: dict[str, list[str]] = {}

        # ── 1. Sector indices ─────────────────────────────────────────────
        print("\n── 1 / 4  Sector indices ───────────────────────────────────────")
        errors = pull_group(
            session, SECTOR_TICKERS, INDEX_FIELDS,
            start_date, end_date, cache_dir,
            label="sector indices", skip_existing=skip_exist,
        )
        if errors:
            all_errors["sector_indices"] = errors

        # ── 2. Benchmark indices ──────────────────────────────────────────
        print("\n── 2 / 4  Benchmark indices ────────────────────────────────────")
        errors = pull_group(
            session, BENCHMARK_TICKERS, INDEX_FIELDS,
            start_date, end_date, cache_dir,
            label="benchmarks", skip_existing=skip_exist,
        )
        if errors:
            all_errors["benchmarks"] = errors

        # ── 3. Commodity futures ──────────────────────────────────────────
        print("\n── 3 / 4  Commodity futures ────────────────────────────────────")
        errors = pull_group(
            session, COMMODITY_TICKERS, INDEX_FIELDS,
            start_date, end_date, cache_dir,
            label="commodities", skip_existing=skip_exist,
        )
        if errors:
            all_errors["commodities"] = errors

        # ── 4. Macro series ───────────────────────────────────────────────
        print("\n── 4 / 4  Macro series ─────────────────────────────────────────")
        errors = pull_group(
            session, MACRO_TICKERS, INDEX_FIELDS,
            start_date, end_date, cache_dir,
            label="macro", skip_existing=skip_exist,
        )
        if errors:
            all_errors["macro"] = errors

        # ── 5. Equity prices (slow, ~45-60 min) ──────────────────────────
        if args.skip_equities:
            print("\n── Equities skipped (--skip-equities) ──────────────────────────")
            print("  Rerun without --skip-equities to pull equity prices.")
        else:
            print("\n── 5 / 5  NIFTY 50 equity prices ──────────────────────────────")
            print("  Note: PX_ADJ_CLOSE adjusted for splits and dividends.")
            print("  Note: this step takes ~45-60 min. Session will resume from last")
            print("  completed ticker if interrupted.\n")

            # Validate tickers first -- ~2% of historical tickers are typically invalid
            valid_equities, invalid = validate_tickers(session, EQUITY_TICKERS)
            if invalid:
                all_errors["equity_invalid_tickers"] = invalid

            errors = pull_equities(
                session, valid_equities, EQUITY_FIELDS,
                start_date, end_date, cache_dir,
                skip_existing=skip_exist,
            )
            if errors:
                all_errors["equities"] = errors

    finally:
        # Always stop the session cleanly, even if an exception was raised
        session.stop()
        print("\nBloomberg session closed.")

    # ── Verify outputs ────────────────────────────────────────────────────
    verify_outputs(cache_dir)

    # ── Report errors ─────────────────────────────────────────────────────
    if all_errors:
        print("\n── Warnings / failed pulls ─────────────────────────────────────")
        for dataset, errors in all_errors.items():
            preview = ", ".join(str(e) for e in errors[:10])
            suffix  = f" ... ({len(errors) - 10} more)" if len(errors) > 10 else ""
            print(f"  {dataset}: {len(errors)} failed  →  {preview}{suffix}")
        print("\n  Rerun the script; already-pulled tickers will be skipped.")
        print("  For persistent failures, run --validate to check field availability.")
    else:
        print("\n✅  All pulls completed without errors.")


if __name__ == "__main__":
    main()
