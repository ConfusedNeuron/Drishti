# Notebook 01 — Data Pull
> Run in: **BQuant (Bloomberg hosted Python environment at FRTL)**
> Output artifacts: `equities_returns.parquet`, `sector_returns.parquet`, `commodity_returns.parquet`, `macro_series.parquet`

---

## Cell 1 [MARKDOWN]

# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti is a local-first quantitative risk research platform for Indian equity portfolios. It imports a Zerodha portfolio, pulls Bloomberg data via BLPAPI, computes multi-method market risk (VaR, ES, backtesting), researches commodity→sector volatility spillover using DCC-GARCH and Diebold-Yilmaz connectedness, detects volatility regimes with a Hidden Markov Model, and surfaces findings through a web dashboard and an MCP-grounded AI copilot.

**Two-tier architecture**
- **BQuant** (this environment): heavy cross-sectional research — pulls NIFTY 200 universe, runs DCC-GARCH, Diebold-Yilmaz, HMM, IC/Granger, walk-forward backtests. Exports artifacts (JSON/Parquet) for the local app.
- **Local app** (BLPAPI + FastAPI): pulls NIFTY 50 + sector indices + commodities + macro, caches locally, serves the risk dashboard.

**Data source**: Bloomberg Terminal, FRTL, IIM Calcutta. For academic research only — do not redistribute.

---

## Cell 2 [MARKDOWN]

## Notebook 01 — Data Pull

**What this notebook does:**
Pulls all time-series data needed for downstream research notebooks using the BQL API. This notebook is the single source of truth for raw data — all other notebooks load from the parquet files exported here.

**Data pulled:**
| Series | Tickers | Purpose |
|--------|---------|---------|
| NIFTY 50 member equity returns | NIFTY Index members | Cross-sectional IC, Granger, HMM features |
| Sector indices | NSEOILGS, NSEMETAL, NSEFMCG, NSEIT, NSEBANK | DCC-GARCH, Diebold-Yilmaz targets |
| Commodity futures (front-month) | CO1, CL1, GC1, HG1, NG1 | Commodity factors for spillover research |
| Macro series | USDINR, GIND10YR, INVIXN | Macro factors + HMM features |
| NIFTY 50 benchmark | NIFTY Index | Beta, correlation baseline |

**Date range:** 2018-01-01 to present (~7 years, covers COVID 2020 and 2022 drawdown)

**Output files saved to:** `/bquant/data/` (adjust path to your BQuant workspace)

---

## Cell 3 [CODE]

```python
# ── Imports ────────────────────────────────────────────────────────────────
import bql
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# BQL service — connects to Bloomberg data in the BQuant environment
bq = bql.Service()

# Output directory for exported artifacts (adjust to your BQuant workspace path)
OUTPUT_DIR = Path("/bquant/data/drishti")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"BQL service initialized.")
print(f"Artifacts will be saved to: {OUTPUT_DIR}")
```

---

## Cell 4 [MARKDOWN]

### Date range and universe definition

We use 2018–present to capture two major stress events:
- **COVID crash** — Feb to Apr 2020 (peak drawdown ~35%)
- **2022 drawdown** — Jan to Jun 2022 (rate hike cycle + global risk-off)

Having both events is essential for DCC-GARCH crisis correlation analysis and HMM regime validation. Fewer than 5 years would give insufficient OOS samples for walk-forward testing.

---

## Cell 5 [CODE]

```python
# ── Date range ──────────────────────────────────────────────────────────────
START_DATE = "2018-01-01"
END_DATE   = "0d"          # BQL: "0d" = today

DATE_RANGE = bq.func.range(START_DATE, END_DATE)

# ── Universe: NIFTY 50 members ──────────────────────────────────────────────
# Using index membership at each date avoids survivorship bias.
# BQuant resolves point-in-time membership via univ.members().
nifty50_univ = bq.univ.members("NIFTY Index")

print("Universe: NIFTY 50 members (point-in-time via BQuant)")
print(f"Date range: {START_DATE} to today")
```

---

## Cell 6 [MARKDOWN]

### Pull 1: NIFTY 50 equity adjusted close prices

`px_last` with `fill='prev'` forward-fills non-trading days (weekends, holidays). `.pct_change()` converts levels to daily simple returns. We request adjusted prices to account for corporate actions (splits, dividends).

---

## Cell 7 [CODE]

```python
# ── Pull equity returns for NIFTY 50 universe ───────────────────────────────
equity_price_field = bq.data.px_last(
    dates=DATE_RANGE,
    fill="prev",
    currency="INR",
)

equity_req  = bql.Request(equity_price_field, nifty50_univ)
equity_data = bq.execute(equity_req)

# Combine to wide DataFrame: rows = dates, columns = tickers
equity_prices = bql.combined_df(equity_data).unstack("DATE").T
equity_prices.index = pd.to_datetime(equity_prices.index)
equity_prices.index.name = "date"

# Daily simple returns (fill forward prices before differencing)
equity_returns = equity_prices.ffill().pct_change().dropna(how="all")

print(f"Equity returns shape: {equity_returns.shape}")
print(f"Date range: {equity_returns.index[0].date()} to {equity_returns.index[-1].date()}")
print(f"Tickers: {list(equity_returns.columns[:5])} … ({equity_returns.shape[1]} total)")
```

---

## Cell 8 [MARKDOWN]

### Pull 2: Sector indices

These are the primary spillover targets — we test how commodity and macro shocks transmit into each sector. Banks are excluded as a direct commodity target because the commodity→CPI→RBI repo→bank valuation channel is mediated and captured via the G-Sec yield factor instead.

---

## Cell 9 [CODE]

```python
# ── Sector index tickers ────────────────────────────────────────────────────
SECTOR_TICKERS = {
    "energy":  "NSEOILGS Index",
    "metals":  "NSEMETAL Index",
    "fmcg":    "NSEFMCG Index",
    "it":      "NSEIT Index",
    # Banks excluded: commodity→rates channel captured via GIND10YR factor
}

sector_price_field = bq.data.px_last(dates=DATE_RANGE, fill="prev")
sector_req  = bql.Request(sector_price_field, list(SECTOR_TICKERS.values()))
sector_data = bq.execute(sector_req)

sector_prices = bql.combined_df(sector_data).unstack("DATE").T
sector_prices.index = pd.to_datetime(sector_prices.index)

# Rename columns from Bloomberg tickers to short labels
ticker_to_label = {v: k for k, v in SECTOR_TICKERS.items()}
sector_prices.rename(columns=ticker_to_label, inplace=True)

sector_returns = sector_prices.ffill().pct_change().dropna(how="all")

print("Sector returns:")
print(sector_returns.describe().round(4))
```

---

## Cell 10 [MARKDOWN]

### Pull 3: Commodity futures (front-month continuous)

Front-month continuous contracts embed roll returns when the contract rolls to the next expiry. We document this but do not roll-adjust — roll bias is small for daily return analysis and Bloomberg's continuous contract series handles the mechanical roll.

---

## Cell 11 [CODE]

```python
# ── Commodity futures ────────────────────────────────────────────────────────
COMMODITY_TICKERS = {
    "brent":  "CO1 Comdty",   # Brent crude — largest driver of Indian input costs
    "wti":    "CL1 Comdty",   # WTI crude — global benchmark; test vs. Brent
    "gold":   "GC1 Comdty",   # Safe-haven factor; Indian equity-gold rotation
    "copper": "HG1 Comdty",   # Global growth proxy; leads metals/industrials
    "natgas": "NG1 Comdty",   # Input cost for fertiliser, power, city gas
}

commodity_price_field = bq.data.px_last(dates=DATE_RANGE, fill="prev")
commodity_req  = bql.Request(commodity_price_field, list(COMMODITY_TICKERS.values()))
commodity_data = bq.execute(commodity_req)

commodity_prices = bql.combined_df(commodity_data).unstack("DATE").T
commodity_prices.index = pd.to_datetime(commodity_prices.index)

ticker_to_label = {v: k for k, v in COMMODITY_TICKERS.items()}
commodity_prices.rename(columns=ticker_to_label, inplace=True)

commodity_returns = commodity_prices.ffill().pct_change().dropna(how="all")

print("Commodity returns:")
print(commodity_returns.describe().round(4))
```

---

## Cell 12 [MARKDOWN]

### Pull 4: Macro series

- **USD/INR**: currency factor — exporters (IT, Pharma) benefit from INR weakness; importers (Energy, FMCG) are hurt.
- **India 10Y G-Sec yield**: rate factor — use first-difference (yield change) not pct_change (rate is a level, not a price).
- **India VIX**: implied volatility — key HMM feature; spikes signal regime transitions.

---

## Cell 13 [CODE]

```python
# ── Macro series ─────────────────────────────────────────────────────────────
MACRO_TICKERS = {
    "usdinr":   "USDINR Curncy",
    "gsec10y":  "GIND10YR Index",
    "indiavix": "INVIXN Index",
}

macro_price_field = bq.data.px_last(dates=DATE_RANGE, fill="prev")
macro_req  = bql.Request(macro_price_field, list(MACRO_TICKERS.values()))
macro_data = bq.execute(macro_req)

macro_levels = bql.combined_df(macro_data).unstack("DATE").T
macro_levels.index = pd.to_datetime(macro_levels.index)

ticker_to_label = {v: k for k, v in MACRO_TICKERS.items()}
macro_levels.rename(columns=ticker_to_label, inplace=True)
macro_levels = macro_levels.ffill()

# USD/INR and VIX: use pct_change (they behave like prices)
# G-Sec yield: use first-difference (it is a rate level, not a price)
macro_returns = macro_levels.pct_change()
macro_returns["gsec10y"] = macro_levels["gsec10y"].diff()   # overwrite with level change

macro_returns = macro_returns.dropna(how="all")

print("Macro series — first rows:")
print(macro_returns.head())
```

---

## Cell 14 [MARKDOWN]

### Data quality checks

Before exporting, we verify:
1. No ticker has >5% missing observations (a common BLPAPI entitlement issue).
2. Date ranges are aligned — all series cover the same trading days.
3. No obvious data errors (extreme returns > 50% in a single day flagged for inspection).

---

## Cell 15 [CODE]

```python
# ── Data quality checks ──────────────────────────────────────────────────────

def check_missing(df: pd.DataFrame, label: str, threshold: float = 0.05):
    miss = df.isnull().mean()
    bad  = miss[miss > threshold]
    print(f"\n{label} — missing > {threshold*100:.0f}%:")
    if bad.empty:
        print("  ✅ All OK")
    else:
        print(bad.to_string())
    return bad.index.tolist()

# Check each dataset
bad_equity    = check_missing(equity_returns,    "Equity returns")
bad_sector    = check_missing(sector_returns,    "Sector returns")
bad_commodity = check_missing(commodity_returns, "Commodity returns")
bad_macro     = check_missing(macro_returns,     "Macro series")

# Flag extreme daily returns (|return| > 30%) — likely data errors
def flag_extremes(df: pd.DataFrame, threshold: float = 0.30):
    extremes = (df.abs() > threshold).any()
    flagged  = extremes[extremes].index.tolist()
    if flagged:
        print(f"\n⚠️  Extreme returns (>{threshold*100:.0f}%/day): {flagged}")
    else:
        print(f"\n✅ No extreme returns found (threshold: {threshold*100:.0f}%/day)")

flag_extremes(equity_returns)
flag_extremes(commodity_returns)
```

---

## Cell 16 [MARKDOWN]

### Align to common trading dates

All downstream notebooks require aligned DataFrames (same date index). We align on the intersection of valid trading dates across all series — this removes non-trading days where any series has a gap.

---

## Cell 17 [CODE]

```python
# ── Align all series to common trading dates ─────────────────────────────────
# Drop tickers with too many missing values
if bad_equity:
    equity_returns = equity_returns.drop(columns=bad_equity, errors="ignore")

# Find common date range
common_start = max(
    equity_returns.index.min(),
    sector_returns.index.min(),
    commodity_returns.index.min(),
    macro_returns.index.min(),
)
common_end = min(
    equity_returns.index.max(),
    sector_returns.index.max(),
    commodity_returns.index.max(),
    macro_returns.index.max(),
)

def trim(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[common_start:common_end].dropna(how="all")

equity_returns    = trim(equity_returns)
sector_returns    = trim(sector_returns)
commodity_returns = trim(commodity_returns)
macro_returns     = trim(macro_returns)

print(f"Aligned date range: {common_start.date()} to {common_end.date()}")
print(f"  Equity:    {equity_returns.shape}")
print(f"  Sectors:   {sector_returns.shape}")
print(f"  Commodities: {commodity_returns.shape}")
print(f"  Macro:     {macro_returns.shape}")
```

---

## Cell 18 [MARKDOWN]

### Export to Parquet

Parquet is column-oriented, compressed, and preserves dtypes — ideal for large financial time-series. These files are the inputs for notebooks 02–07. Export them to your BQuant workspace, then download to `data/cache/research_artifacts/` on your local machine.

---

## Cell 19 [CODE]

```python
# ── Export to Parquet ────────────────────────────────────────────────────────
equity_returns.to_parquet(OUTPUT_DIR / "equities_returns.parquet")
sector_returns.to_parquet(OUTPUT_DIR / "sector_returns.parquet")
commodity_returns.to_parquet(OUTPUT_DIR / "commodity_returns.parquet")
macro_returns.to_parquet(OUTPUT_DIR / "macro_series.parquet")

print("✅ Exported:")
for f in OUTPUT_DIR.glob("*.parquet"):
    size_kb = f.stat().st_size / 1024
    print(f"  {f.name:40s}  {size_kb:6.1f} KB")

print(f"\nNext: run notebooks 02–07 using these files as inputs.")
print(f"Then copy {OUTPUT_DIR} to data/cache/research_artifacts/ on your laptop.")
```
