"""Regenerate the equities section of data/mappings/yahoo_tickers.json from the
v2 universe so the weekly yfinance gap-fill covers all ~433 names, not 48.

Bloomberg NSE equity codes usually equal the NSE symbol (Yahoo: SYMBOL.NS);
OVERRIDES carries the known divergences (CLAUDE.md confirmed list, inverted).
--validate batch-probes Yahoo and prints failures for manual triage.

Usage:  PYTHONPATH=. python scripts/build_yahoo_map_v2.py [--validate]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.research.universe import load_universe

MAPPING_PATH = Path("data/mappings/yahoo_tickers.json")

OVERRIDES = {
    "HDFCB": "HDFCBANK", "INFO": "INFY", "ICICIBC": "ICICIBANK", "KMB": "KOTAKBANK",
    "BAF": "BAJFINANCE", "HUVR": "HINDUNILVR", "HCLT": "HCLTECH", "WPRO": "WIPRO",
    "NEST": "NESTLEIND", "APNT": "ASIANPAINT", "TTMT": "TATAMOTORS", "HNDL": "HINDALCO",
    "PWGR": "POWERGRID", "TATA": "TATASTEEL", "TTAN": "TITAN", "MSIL": "MARUTI",
}


def yahoo_candidate(bbg_ticker: str) -> str:
    code = bbg_ticker.split(" ")[0]
    return f"{OVERRIDES.get(code, code)}.NS"


def build_equity_map(tickers) -> dict[str, str]:
    return {t: yahoo_candidate(t) for t in sorted(tickers)}


def validate(equity_map: dict[str, str]) -> list[str]:
    import yfinance as yf
    symbols = list(equity_map.values())
    data = yf.download(symbols, period="5d", progress=False, group_by="ticker")
    bad = [s for s in symbols if s not in data.columns.get_level_values(0)
           or data[s]["Close"].dropna().empty]
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true", help="probe Yahoo for every candidate")
    args = ap.parse_args()

    universe = load_universe()
    if not universe:
        raise SystemExit("universe_v2.json missing — run on a machine with the v2 cache")

    mapping = json.loads(MAPPING_PATH.read_text())
    mapping["equities"] = build_equity_map(universe.keys())
    MAPPING_PATH.write_text(json.dumps(mapping, indent=2) + "\n")
    print(f"Wrote {len(mapping['equities'])} equity mappings to {MAPPING_PATH}")

    if args.validate:
        bad = validate(mapping["equities"])
        print(f"{len(bad)} candidates failed Yahoo probe:" if bad else "All candidates resolved on Yahoo.")
        for s in bad:
            print("  ", s)


if __name__ == "__main__":
    main()
