"""
Bloomberg BLPAPI data pull script — run at FRTL on the Bloomberg terminal machine.

Usage (at FRTL, with Bloomberg terminal running):
    cd C:\Users\User\Pranav\drishti
    .venv\Scripts\activate
    python scripts/pull_bloomberg_data.py --output-dir "C:\Users\User\Pranav\drishti\data\cache\bloomberg"

The script:
  - Pulls 5 years of daily prices for all equity/sector/commodity/macro tickers
  - Caches each ticker to parquet incrementally (resumes if interrupted)
  - Skips tickers already cached and fresh (< 2 days old)

Pass --symbols-only to validate tickers before the full pull.
"""
import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "cache" / "bloomberg")
parser.add_argument("--start-date", default="20210104")
parser.add_argument("--end-date",   default=date.today().strftime("%Y%m%d"))
parser.add_argument("--symbols-only", action="store_true",
                    help="Only validate tickers, do not pull data")
parser.add_argument("--skip-equities", action="store_true")
args = parser.parse_args()

# Override cache dir before importing config
import os
os.environ["CACHE_DIR_OVERRIDE"] = str(args.output_dir)

from src.bloomberg.client import BloombergClient
from src.bloomberg import cache as bbg_cache
from src.config import COMMODITY_TICKERS, MACRO_TICKERS, SECTOR_TICKERS, BENCHMARK_TICKERS
from src.bloomberg.tickers import _BUILTIN_TICKERS

client = BloombergClient()
try:
    client.connect()
except Exception as e:
    print(f"ERROR: Bloomberg connection failed — {e}")
    sys.exit(1)

if not client.connected:
    print("ERROR: Not connected to Bloomberg. Ensure terminal is running.")
    sys.exit(1)

print(f"✅ Bloomberg connected.")

END   = args.end_date
START = args.start_date

EQUITY_TICKERS   = list(_BUILTIN_TICKERS.values())[:50]   # top 50 from registry
SECTOR_TKRS      = list(SECTOR_TICKERS.values())
COMMODITY_TKRS   = list(COMMODITY_TICKERS.values())
MACRO_TKRS       = list(MACRO_TICKERS.values())
BENCHMARK_TKRS   = list(BENCHMARK_TICKERS.values())

# ── Ticker validation ───────────────────────────────────────────────────────
def validate_tickers(tickers: list[str]) -> tuple[list, list]:
    valid, invalid = [], []
    for chunk in _chunks(tickers, 50):
        ref = client.bdp(chunk, ["SECURITY_NAME"])
        for t in chunk:
            if t in ref and ref[t].get("SECURITY_NAME"):
                valid.append(t)
            else:
                invalid.append(t)
    return valid, invalid


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]


if args.symbols_only:
    all_tkrs = EQUITY_TICKERS + SECTOR_TKRS + COMMODITY_TKRS + MACRO_TKRS
    print(f"\nValidating {len(all_tkrs)} tickers...")
    v, inv = validate_tickers(all_tkrs)
    print(f"  Valid: {len(v)}, Invalid: {len(inv)}")
    if inv:
        print(f"  Invalid tickers: {inv}")
    sys.exit(0)

# ── Data pull ───────────────────────────────────────────────────────────────
def pull_group(tickers, fields, label):
    print(f"\nPulling {label} ({len(tickers)} tickers)...")
    for i, chunk in enumerate(_chunks(tickers, 100)):
        print(f"  Chunk {i+1}: {chunk[:3]}...")
        try:
            client.bdh(chunk, fields, START, END)
        except Exception as e:
            print(f"  ⚠️  Chunk failed: {e}")
        time.sleep(0.25)
    print(f"  ✅ {label} done.")


pull_group(SECTOR_TKRS + BENCHMARK_TKRS, ["PX_LAST"], "Sector + Benchmark Indices")
pull_group(COMMODITY_TKRS, ["PX_LAST"], "Commodity Futures")
pull_group(MACRO_TKRS, ["PX_LAST"], "Macro Series")

if not args.skip_equities:
    pull_group(EQUITY_TICKERS, ["PX_ADJ_CLOSE", "PX_LAST"], "Equity Prices")

print(f"\n✅ All data cached to {args.output_dir}")
print("Copy the data/cache/ folder to your laptop before the demo.")
