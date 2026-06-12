r"""
Drishti v2 Bloomberg pull — survivorship-free Nifty100 + Midcap150 universe since 2000.

Run at FRTL from the repo root (Windows):
  python scripts\pull_drishti_v2.py --validate          # field/ticker sanity, no big pulls
  python scripts\pull_drishti_v2.py --discover           # index membership -> universe manifest
  python scripts\pull_drishti_v2.py --indices --commodities --macro
  python scripts\pull_drishti_v2.py --equities           # the big one
  python scripts\pull_drishti_v2.py --sectors            # BDP GICS sector for whole universe
  python scripts\pull_drishti_v2.py --annual             # optional fundamentals
  python scripts\pull_drishti_v2.py --retry-failed       # re-attempt failure log

Writes ONLY to data/cache/bloomberg_v2/. Never touches data/cache/bloomberg/.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V2_DIR = ROOT / "data" / "cache" / "bloomberg_v2"
META_DIR = V2_DIR / "meta"
FAILED_LOG = META_DIR / "failed_v2.json"
UNIVERSE_MANIFEST = META_DIR / "universe_v2.json"

PULL_START = "20000101"
PULL_END = date.today().strftime("%Y%m%d")

MEMBERSHIP_INDICES = ["NSE100 Index", "NSEMD150 Index"]
MEMBERSHIP_FALLBACKS = ["NSEMCAP Index", "NSE500 Index"]   # if NSEMD150 has no pre-2016 history

EQUITY_DAILY_FIELDS = ["PX_LAST", "PX_VOLUME", "PE_RATIO", "PX_TO_BOOK_RATIO", "CUR_MKT_CAP"]
INDEX_FIELDS = ["PX_LAST", "PE_RATIO", "PX_TO_BOOK_RATIO"]   # valuation needed for events study
SIMPLE_FIELDS = ["PX_LAST"]                                   # commodities, macro

INDEX_TICKERS = [
    # v1 set
    "NSENRG Index", "NSEMET Index", "NSEFMCG Index", "NSEIT Index", "NSEBANK Index",
    "NSEAUTO Index", "NSEPHRM Index", "NSEREALTY Index", "NSEPSBK Index",
    "NSE200 Index", "NIFTY Index", "SENSEX Index", "NIFTYJR Index",
    # v2 additions (verified in data/csv/all nse index.csv)
    "NSE100 Index", "NSE500 Index", "NSEMD150 Index", "NSEMCAP Index", "NIFTYM50 Index",
    "NSESMCP Index", "NSES250 Index", "NSESM50 Index", "NSELM250 Index", "NSEMDSM Index",
    "NSEFIN Index", "NSEINFR Index", "NSECON Index", "NSECMD Index", "NSEMED Index", "NSEPSE Index",
]

COMMODITY_TICKERS = [
    # v1 set (extend history to 2000)
    "CO1 Comdty", "CL1 Comdty", "GC1 Comdty", "HG1 Comdty", "NG1 Comdty", "S 1 Comdty", "W 1 Comdty",
    # v2 additions — VERIFY AT TERMINAL via SECF before the big pull; alternates in comments
    "SI1 Comdty",       # COMEX silver front
    "LMAHDS03 Comdty",  # LME aluminium 3M; alt: LA1 Comdty
    "LMZSDS03 Comdty",  # LME zinc 3M;     alt: LX1 Comdty
    "SB1 Comdty",       # ICE sugar #11
    "CT1 Comdty",       # ICE cotton #2
    "KO1 Comdty",       # Bursa crude palm oil; alt: PAL... verify
    "XW1 Comdty",       # Newcastle coal; alts: API21MON Index, XA1 Comdty — verify
    "IOE1 Comdty",      # SGX iron ore 62%; alt: SCO1 Comdty — verify
]

MACRO_TICKERS = ["USDINR Curncy", "GIND10YR Index", "INVIXN Index", "DXY Curncy"]

# Reuse v1 plumbing — available on FRTL (tqdm installed); gracefully absent on Mac for dry import.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from pull_drishti_data import (
        open_session, bdh, bdp, chunks, element_to_python,
        read_cached, write_to_cache, ticker_to_filename,
    )
except ImportError:
    open_session = bdh = bdp = chunks = element_to_python = read_cached = write_to_cache = ticker_to_filename = None  # type: ignore


if __name__ == "__main__":
    pass
