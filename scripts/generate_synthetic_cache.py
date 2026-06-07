"""
Generate synthetic Bloomberg price cache for offline demo.

Simulates 5 years of daily returns for:
  - 12 NIFTY sample portfolio stocks (correlated via sector factor model)
  - 4 sector indices (Energy, Metals, FMCG, IT)
  - 5 commodity factors (Brent, WTI, Gold, Copper, NatGas)
  - 3 macro factors (USD/INR, G-Sec 10Y, India VIX)

Run from the drishti/ directory:
    python scripts/generate_synthetic_cache.py

Output: data/cache/bloomberg/{equities,indices,commodities,macro}/*.parquet
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from datetime import date, timedelta

from src.bloomberg.cache import write_cache
from src.bloomberg.tickers import _BUILTIN_TICKERS
from src.config import (
    COMMODITY_TICKERS, MACRO_TICKERS, SECTOR_TICKERS,
)

SEED = 42
rng = np.random.default_rng(SEED)

# ── Date range ─────────────────────────────────────────────────────────────
END   = date(2026, 5, 30)
START = date(2021, 1, 4)

def _trading_dates(start: date, end: date) -> pd.DatetimeIndex:
    all_dates = pd.date_range(start, end, freq="B")   # Mon-Fri
    return all_dates


dates = _trading_dates(START, END)
T = len(dates)
print(f"Generating {T} trading days ({START} → {END})")


# ── Factor model for correlated returns ────────────────────────────────────

def simulate_garch(n: int, omega=1e-6, alpha=0.08, beta=0.88, mu=0.0) -> np.ndarray:
    """Simple GARCH(1,1) path."""
    r = np.zeros(n)
    sigma2 = omega / (1 - alpha - beta)
    for t in range(n):
        r[t] = mu + np.sqrt(sigma2) * rng.standard_normal()
        sigma2 = omega + alpha * r[t]**2 + beta * sigma2
    return r


# Market factor (NIFTY)
market = simulate_garch(T, mu=4e-4)

# Sector factors
sector_factors = {
    "energy":  simulate_garch(T, mu=3e-4)  + 0.6  * market,
    "metals":  simulate_garch(T, mu=2e-4)  + 0.7  * market,
    "fmcg":    simulate_garch(T, mu=3e-4)  + 0.45 * market,
    "it":      simulate_garch(T, mu=5e-4)  + 0.5  * market,
    "banks":   simulate_garch(T, mu=3e-4)  + 0.75 * market,
    "pharma":  simulate_garch(T, mu=2e-4)  + 0.35 * market,
}

# Commodity factors
commodity_factors = {
    "brent":  simulate_garch(T, omega=5e-6, mu=2e-4),
    "wti":    simulate_garch(T, omega=5e-6, mu=2e-4) * 0.92 + 0.08 * simulate_garch(T),
    "gold":   simulate_garch(T, omega=2e-6, mu=1e-4),
    "copper": simulate_garch(T, omega=4e-6, mu=2e-4) + 0.3 * market,
    "natgas": simulate_garch(T, omega=8e-6, mu=0.0),
}

# Macro factors
macro_factors = {
    "usdinr":  -0.3 * market + simulate_garch(T, omega=1e-6, mu=2e-5),
    "gsec10y": np.cumsum(rng.normal(0, 0.005, T)),   # yields as levels
    "indiavix": 15 + np.cumsum(rng.normal(0, 0.3, T)),  # VIX as level
}
# Keep VIX positive
macro_factors["indiavix"] = np.clip(macro_factors["indiavix"], 8, 80)

# COVID crash: Feb-Mar 2020 ... but our start is Jan 2021, so simulate a mini-crash
crash_start = int(T * 0.12)
crash_len = 20
for k in sector_factors:
    sector_factors[k][crash_start:crash_start+crash_len] -= rng.uniform(0.01, 0.03, crash_len)

# ── Sector index prices ─────────────────────────────────────────────────────
sector_base = {"energy": 11000, "metals": 7500, "fmcg": 60000,
               "it": 35000, "banks": 42000, "pharma": 15000}

def returns_to_prices(returns: np.ndarray, base: float) -> np.ndarray:
    return base * np.cumprod(1 + returns)


print("Writing sector indices...")
for sid, ticker in SECTOR_TICKERS.items():
    if sid not in sector_factors:
        continue
    ret = sector_factors[sid]
    prices = returns_to_prices(ret, sector_base.get(sid, 10000))
    df = pd.DataFrame({"PX_LAST": prices}, index=dates)
    write_cache(ticker, df)

# ── Commodity prices ────────────────────────────────────────────────────────
commodity_base = {"brent": 75.0, "wti": 72.0, "gold": 1900.0,
                  "copper": 4.2, "natgas": 3.5}

print("Writing commodity factors...")
for cid, ticker in COMMODITY_TICKERS.items():
    ret = commodity_factors.get(cid, simulate_garch(T))
    prices = returns_to_prices(ret, commodity_base.get(cid, 100))
    df = pd.DataFrame({"PX_LAST": prices}, index=dates)
    write_cache(ticker, df)

# ── Macro series ─────────────────────────────────────────────────────────────
print("Writing macro series...")
usdinr_base = 74.0
usdinr_prices = returns_to_prices(macro_factors["usdinr"], usdinr_base)

write_cache(MACRO_TICKERS["usdinr"],
            pd.DataFrame({"PX_LAST": usdinr_prices}, index=dates))

# G-Sec yield as level (not returns) — starts at ~6.5%
gsec_level = 6.5 + macro_factors["gsec10y"]
gsec_level = np.clip(gsec_level, 5.0, 9.0)
write_cache(MACRO_TICKERS["gsec10y"],
            pd.DataFrame({"PX_LAST": gsec_level}, index=dates))

# VIX as level
write_cache(MACRO_TICKERS["indiavix"],
            pd.DataFrame({"PX_LAST": macro_factors["indiavix"]}, index=dates))

# ── Equity prices ─────────────────────────────────────────────────────────────
PORTFOLIO_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "TATASTEEL", "ONGC", "WIPRO",
    "SUNPHARMA", "NTPC",
]

SYMBOL_SECTOR = {
    "RELIANCE":   "energy", "ONGC":       "energy",
    "TCS":        "it",     "INFY":       "it",    "WIPRO":  "it",
    "HDFCBANK":   "banks",  "ICICIBANK":  "banks",
    "HINDUNILVR": "fmcg",   "ITC":        "fmcg",
    "TATASTEEL":  "metals",
    "SUNPHARMA":  "pharma",
    "NTPC":       "energy",
}

SYMBOL_BASE_PRICE = {
    "RELIANCE": 2000, "TCS": 3200, "HDFCBANK": 1400, "INFY": 1300,
    "ICICIBANK": 850, "HINDUNILVR": 2400, "ITC": 380, "TATASTEEL": 140,
    "ONGC": 170, "WIPRO": 410, "SUNPHARMA": 1200, "NTPC": 310,
}

print("Writing equity prices...")
for sym in PORTFOLIO_SYMBOLS:
    sector_key = SYMBOL_SECTOR.get(sym, "energy")
    sector_ret = sector_factors.get(sector_key, market)
    # Add idiosyncratic noise
    idio = simulate_garch(T, omega=2e-6, mu=rng.uniform(-1e-4, 5e-4))
    eq_ret = 0.7 * sector_ret + 0.3 * idio
    base = SYMBOL_BASE_PRICE.get(sym, 1000)
    prices = returns_to_prices(eq_ret, base)
    ticker = _BUILTIN_TICKERS.get(sym, f"{sym} IN Equity")
    df = pd.DataFrame({
        "PX_LAST": prices,
        "PX_ADJ_CLOSE": prices,   # same for synthetic data
    }, index=dates)
    write_cache(ticker, df)

# ── Nifty benchmark ────────────────────────────────────────────────────────
nifty_prices = returns_to_prices(market, 17500)
write_cache("NIFTY Index", pd.DataFrame({"PX_LAST": nifty_prices}, index=dates))

print("\n✅ Synthetic cache written.")
print(f"   Location: {ROOT / 'data' / 'cache' / 'bloomberg'}")
print("\nYou can now run: uvicorn src.dashboard.app:app --reload")
print("Then visit: http://localhost:8000")
