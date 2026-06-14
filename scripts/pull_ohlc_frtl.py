r"""
Drishti OHLC pull — Open/High/Low/Close for extreme-value volatility estimators.

The v2 cache stores PX_LAST only. Parkinson / Garman-Klass / Rogers-Satchell
estimators (FRM Wk7) need the full OHLC range, so this script pulls
PX_OPEN, PX_HIGH, PX_LOW, PX_LAST for the whole v2 universe into a separate
ohlc/ subtree. Notebook 13's extreme-value section reads from there and skips
gracefully if the files are absent.

Run at FRTL from the repo root (Windows):
  python scripts\pull_ohlc_frtl.py --validate         # 5-day field sanity, no big pulls
  python scripts\pull_ohlc_frtl.py --indices --commodities
  python scripts\pull_ohlc_frtl.py --equities          # all 433 from the v2 universe manifest
  python scripts\pull_ohlc_frtl.py --retry-failed      # re-attempt the failure log

Writes ONLY to data/cache/bloomberg_v2/ohlc/. Never touches the close-only
parquets the rest of Drishti already depends on. Resumable: skips any ticker
whose ohlc parquet already exists.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "data" / "cache" / "bloomberg_v2"
OHLC_DIR = V2_DIR / "ohlc"
META_DIR = V2_DIR / "meta"
FAILED_LOG = META_DIR / "failed_ohlc.json"
UNIVERSE_MANIFEST = META_DIR / "universe_v2.json"

PULL_START = "20000101"
PULL_END = date.today().strftime("%Y%m%d")

# The four price points every extreme-value estimator needs. A series missing
# one (e.g. a synthetic index with no open) just comes back with that column NaN.
OHLC_FIELDS = ["PX_OPEN", "PX_HIGH", "PX_LOW", "PX_LAST"]

# Reuse v2 ticker registry + the v1 BDH/cache plumbing. Both import cleanly only
# at FRTL (blpapi present); on Mac the import degrades to None for a dry --help.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from pull_drishti_v2 import INDEX_TICKERS, COMMODITY_TICKERS
    from pull_drishti_data import (
        open_session, bdh, chunks, write_to_cache, ticker_to_filename,
    )
except ImportError:
    INDEX_TICKERS = COMMODITY_TICKERS = []          # type: ignore
    open_session = bdh = chunks = write_to_cache = ticker_to_filename = None  # type: ignore


def _log_failure(ticker: str, group: str, err: str) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    log = json.loads(FAILED_LOG.read_text()) if FAILED_LOG.exists() else {}
    log[ticker] = {"group": group, "error": str(err)[:300], "at": date.today().isoformat()}
    FAILED_LOG.write_text(json.dumps(log, indent=1))


def pull_ohlc_group(session, tickers: list[str], subdir: str,
                    batch: int = 25, equity_adjust: bool = False) -> None:
    """BDH OHLC for a ticker group into ohlc/<subdir>/. Mirrors pull_drishti_v2.pull_group_v2."""
    out_dir = OHLC_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [t for t in tickers if not (out_dir / f"{ticker_to_filename(t)}.parquet").exists()]
    print(f"[ohlc/{subdir}] {len(todo)}/{len(tickers)} to pull")
    for grp in chunks(todo, batch):
        try:
            if equity_adjust:
                # Same adjustment as the v2 equity close pull, so OHLC aligns with PX_LAST.
                df, errors_list = bdh(session, grp, OHLC_FIELDS, PULL_START, PULL_END,
                                      adj_split=True, adj_normal=True)
            else:
                df, errors_list = bdh(session, grp, OHLC_FIELDS, PULL_START, PULL_END)
        except Exception as e:
            for t in grp:
                _log_failure(t, subdir, str(e))
            continue
        error_set = set(errors_list)
        if not df.empty and "ticker" in df.columns:
            for t in grp:
                if t in error_set:
                    _log_failure(t, subdir, "Bloomberg security error")
                    continue
                t_df = df[df["ticker"] == t].drop(columns=["ticker"])
                if t_df.empty:
                    _log_failure(t, subdir, "empty response")
                else:
                    write_to_cache(out_dir / f"{ticker_to_filename(t)}.parquet", t_df)
        else:
            for t in errors_list:
                _log_failure(t, subdir, "Bloomberg security error")
            for t in grp:
                if t not in error_set:
                    _log_failure(t, subdir, "empty response")


def validate(session) -> None:
    """5-day BDH of OHLC on one known-good name per group + a few index/commodity probes."""
    probes = {
        "equity ohlc":    ["RELIANCE IN Equity", "HDFCB IN Equity"],
        "index ohlc":     ["NIFTY Index", "NSEBANK Index"],
        "commodity ohlc": ["CO1 Comdty", "GC1 Comdty"],
    }
    start = date.today().replace(day=1).strftime("%Y%m%d")
    for label, tickers in probes.items():
        try:
            df, errors = bdh(session, tickers, OHLC_FIELDS, start, PULL_END)
            error_set = set(errors)
            for t in tickers:
                if t in error_set:
                    print(f"  [{label}] {t}: FAIL (security error)")
                elif df.empty or (not df.empty and "ticker" in df.columns and df[df["ticker"] == t].empty):
                    print(f"  [{label}] {t}: FAIL (no data)")
                else:
                    have = [c for c in OHLC_FIELDS if c in df.columns and df[df["ticker"] == t][c].notna().any()]
                    print(f"  [{label}] {t}: OK  fields={have}")
        except Exception as e:
            print(f"  [{label}] batch error: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Drishti OHLC pull for extreme-value volatility estimators.")
    for flag in ["validate", "indices", "commodities", "equities", "retry_failed"]:
        ap.add_argument(f"--{flag.replace('_', '-')}", action="store_true")
    args = ap.parse_args()

    session = open_session()

    if args.validate:
        validate(session)
        return

    if args.indices:
        pull_ohlc_group(session, sorted(set(INDEX_TICKERS)), "indices")
    if args.commodities:
        pull_ohlc_group(session, COMMODITY_TICKERS, "commodities")
    if args.equities:
        universe = json.loads(UNIVERSE_MANIFEST.read_text()) if UNIVERSE_MANIFEST.exists() else {}
        if not universe:
            print("No universe_v2.json — run pull_drishti_v2.py --discover first.")
            return
        pull_ohlc_group(session, sorted(universe), "equities", equity_adjust=True)
    if args.retry_failed and FAILED_LOG.exists():
        log = json.loads(FAILED_LOG.read_text())
        by_group: dict[str, list[str]] = {}
        for t, rec in log.items():
            by_group.setdefault(rec["group"], []).append(t)
        FAILED_LOG.unlink()
        for grp_name, ts in by_group.items():
            pull_ohlc_group(session, ts, grp_name, equity_adjust=(grp_name == "equities"))


if __name__ == "__main__":
    main()
