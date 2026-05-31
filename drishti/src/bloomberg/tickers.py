"""
Zerodha trading symbol → Bloomberg ticker mapping.
Falls back to "{SYMBOL} IN Equity" pattern for unmapped symbols.
"""
from __future__ import annotations
import json
from pathlib import Path

from src.config import MAPPINGS_DIR

_TICKER_FILE = MAPPINGS_DIR / "bloomberg_tickers.json"
_SECTOR_FILE = MAPPINGS_DIR / "sector_map.json"

# Bundled fallback map (common NSE stocks)
_BUILTIN_TICKERS: dict[str, str] = {
    "RELIANCE":  "RELIANCE IN Equity",
    "TCS":       "TCS IN Equity",
    "HDFCBANK":  "HDFCBANK IN Equity",
    "INFY":      "INFY IN Equity",
    "ICICIBANK": "ICICIBANK IN Equity",
    "HINDUNILVR":"HINDUNILVR IN Equity",
    "ITC":       "ITC IN Equity",
    "SBIN":      "SBIN IN Equity",
    "BAJFINANCE":"BAJFINANCE IN Equity",
    "KOTAKBANK": "KOTAKBANK IN Equity",
    "LT":        "LT IN Equity",
    "ASIANPAINT":"ASIANPAINT IN Equity",
    "TITAN":     "TITAN IN Equity",
    "NESTLEIND": "NESTLEIND IN Equity",
    "MARUTI":    "MARUTI IN Equity",
    "ONGC":      "ONGC IN Equity",
    "NTPC":      "NTPC IN Equity",
    "POWERGRID": "POWERGRID IN Equity",
    "WIPRO":     "WIPRO IN Equity",
    "HCLTECH":   "HCLTECH IN Equity",
    "BAJAJ-AUTO":"BJAUT IN Equity",
    "TATAMOTORS":"TATAMOTORS IN Equity",
    "TATASTEEL": "TATASTEEL IN Equity",
    "HINDALCO":  "HINDALCO IN Equity",
    "COALINDIA": "COAL IN Equity",
    "JSWSTEEL":  "JSTL IN Equity",
    "CIPLA":     "CIPLA IN Equity",
    "DRREDDY":   "DRRD IN Equity",
    "SUNPHARMA": "SUNP IN Equity",
    "ADANIENT":  "ADE IN Equity",
    "ADANIPORTS":"ADSEZ IN Equity",
    "ULTRACEMCO":"UTCEM IN Equity",
    "GRASIM":    "GRASIM IN Equity",
    "BRITANNIA": "BRIT IN Equity",
    "EICHERMOT": "EIM IN Equity",
    "HEROMOTOCO":"HMCL IN Equity",
    "DIVISLAB":  "DIVI IN Equity",
    "APOLLOHOSP":"APHS IN Equity",
    "BHARTIARTL":"BHARTI IN Equity",
    "BPCL":      "BPCL IN Equity",
    "IOC":       "IOCL IN Equity",
    "M&M":       "MM IN Equity",
    "TECHM":     "TECHM IN Equity",
    "HDFC":      "HDFC IN Equity",
    "INDUSINDBK":"IIB IN Equity",
    "BAJAJFINSV":"BJFIN IN Equity",
    "UPL":       "UPLL IN Equity",
    "TATACONSUM":"TTMT IN Equity",
}

_BUILTIN_SECTORS: dict[str, str] = {
    "RELIANCE":  "Energy",
    "TCS":       "Information Technology",
    "HDFCBANK":  "Financials",
    "INFY":      "Information Technology",
    "ICICIBANK": "Financials",
    "HINDUNILVR":"Consumer Staples",
    "ITC":       "Consumer Staples",
    "SBIN":      "Financials",
    "BAJFINANCE":"Financials",
    "KOTAKBANK": "Financials",
    "LT":        "Industrials",
    "ASIANPAINT":"Materials",
    "TITAN":     "Consumer Discretionary",
    "NESTLEIND": "Consumer Staples",
    "MARUTI":    "Consumer Discretionary",
    "ONGC":      "Energy",
    "NTPC":      "Utilities",
    "POWERGRID": "Utilities",
    "WIPRO":     "Information Technology",
    "HCLTECH":   "Information Technology",
    "TATAMOTORS":"Consumer Discretionary",
    "TATASTEEL": "Materials",
    "HINDALCO":  "Materials",
    "COALINDIA": "Energy",
    "JSWSTEEL":  "Materials",
    "CIPLA":     "Health Care",
    "DRREDDY":   "Health Care",
    "SUNPHARMA": "Health Care",
    "BHARTIARTL":"Communication Services",
    "BPCL":      "Energy",
    "IOC":       "Energy",
    "M&M":       "Consumer Discretionary",
    "TECHM":     "Information Technology",
}


def _load_json(path: Path, default: dict) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return default


class TickerRegistry:
    def __init__(self):
        extra = _load_json(_TICKER_FILE, {})
        self._map: dict[str, str] = {**_BUILTIN_TICKERS, **extra}
        extra_s = _load_json(_SECTOR_FILE, {})
        self._sectors: dict[str, str] = {**_BUILTIN_SECTORS, **extra_s}

    def resolve(self, zerodha_symbol: str) -> str:
        sym = zerodha_symbol.upper()
        if sym in self._map:
            return self._map[sym]
        return f"{sym} IN Equity"

    def sector(self, zerodha_symbol: str) -> str:
        return self._sectors.get(zerodha_symbol.upper(), "Unknown")

    def all_mappings(self) -> dict[str, str]:
        return dict(self._map)


registry = TickerRegistry()
