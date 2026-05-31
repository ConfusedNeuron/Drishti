# Drishti — Claude Code Context

## What this project is

Drishti is a local-first quant risk research platform for Indian equity portfolios, built as a Financial Risk Management course project at IIM Calcutta (PGDBA Sem 3). It imports a Zerodha portfolio, pulls Bloomberg data, computes market risk, researches commodity factor signals, detects volatility regimes, and exposes everything through a web dashboard and an MCP-grounded AI copilot.

**This is a course demo prototype, not a production system.** All language must be educational and diagnostic — never investment advice.

---

## Current status (as of 2026-06-01)

**Real Bloomberg data is pulled and loaded.** The full NIFTY 50 equity pull, all sector indices, commodities, and macro series are cached at `data/cache/bloomberg/`. The dashboard runs on real data. Synthetic fallback still works for offline development.

### What's working end-to-end
- Bloomberg data pipeline (FRTL → parquet cache → dashboard)
- Portfolio import (sample, CSV, Zerodha)
- All three VaR methods (historical, parametric, GARCH-FHS)
- ES, Kupiec + Christoffersen backtest, component VaR, drawdown, stress scenarios
- HMM regime detection + regime-conditioned VaR
- DCC-GARCH dynamic correlations
- Diebold-Yilmaz connectedness (VAR + generalized FEVD)
- Time-series IC + Granger causality + BH FDR correction
- Deterministic risk memo
- FastAPI backend + Plotly.js single-page dashboard
- 14 unit tests passing

### What's left to build
| Priority | Item | Notes |
|----------|------|-------|
| High | **Walk-forward OOS Sharpe** | `src/research/walk_forward.py` + `/api/research/walkforward` route. Spec in `notebooks/05_walk_forward_backtest.md`. |
| High | **Risk MCP server** | `mcp/server.py` + `mcp/tools.py`. All analytics exposed as MCP tools for AI copilot. |
| Medium | **Fix JS regime tab bug** | `src/dashboard/static/index.html` — `showTab` override at bottom of file doesn't work; regime data loads on every tab switch instead of once. |
| Medium | **Rolling Diebold-Yilmaz route** | `rolling_spillover()` already implemented in `src/research/diebold_yilmaz.py`; needs an API route and dashboard chart. |
| Low | **News RSS + FinBERT** | `src/research/news.py` — Cogencis/SEBI RSS + sentiment scoring. Lower priority for demo. |
| Low | **BQuant notebooks** | Markdown specs in `notebooks/01-07.md`. User fills in cells manually in BQuant environment at FRTL. |

---

## Two-tier architecture

```
BQuant (Bloomberg hosted Python)          Local machine (this repo)
─────────────────────────────────         ──────────────────────────
bql API → NIFTY 200 cross-section    →    artifacts (JSON/Parquet)
HMM, DCC-GARCH, Diebold-Yilmaz      →    loaded by src/research/
Walk-forward IC/Granger              →    served via FastAPI
```

- **BQuant notebooks** (`notebooks/`) run inside Bloomberg's hosted environment at FRTL. They export JSON/Parquet artifacts to `data/cache/research_artifacts/`.
- **Local app** (`src/`) uses the parquet cache at `data/cache/bloomberg/` and serves the dashboard.
- Synthetic fallback (`scripts/generate_synthetic_cache.py`) for offline development.

---

## Directory layout

```
drishti/
├── src/
│   ├── config.py                  # Paths, Bloomberg ticker registry, stress scenarios
│   ├── models.py                  # Dataclasses: Holding, VaRResult, BacktestResult, etc.
│   ├── bloomberg/
│   │   ├── cache.py               # Parquet cache (read/write/freshness/category routing)
│   │   ├── client.py              # BLPAPI session + BDH/BDP; falls back to cache
│   │   └── tickers.py             # Zerodha symbol → Bloomberg ticker mapping
│   ├── portfolio/
│   │   └── importer.py            # Load from sample JSON / CSV / Zerodha Kite API
│   ├── risk/
│   │   ├── returns.py             # Return matrix builder + factor/sector series loaders
│   │   ├── var.py                 # Historical (non-overlapping), Parametric, GARCH-FHS VaR
│   │   ├── es.py                  # Expected Shortfall
│   │   ├── backtest.py            # Kupiec LR test + Christoffersen independence test
│   │   ├── contribution.py        # Component VaR (marginal contribution)
│   │   ├── drawdown.py            # Max drawdown, current drawdown, recovery date
│   │   └── stress.py              # 5 stress scenarios (COVID/rate/crude/INR/election)
│   ├── research/
│   │   ├── hmm.py                 # 2-state Gaussian HMM; walk-forward; canonical labeling
│   │   ├── ic.py                  # Time-series IC + Granger causality + BH FDR correction
│   │   ├── dcc_garch.py           # DCC-GARCH dynamic correlations (2-step Engle 2002)
│   │   └── diebold_yilmaz.py      # Connectedness index (VAR + Pesaran-Shin GFEVD)
│   ├── copilot/
│   │   └── memo.py                # Deterministic risk memo (no LLM required)
│   └── dashboard/
│       ├── app.py                 # FastAPI app entry point
│       ├── routes/                # portfolio / risk / research / copilot routes
│       └── static/index.html      # Single-page Plotly.js dashboard (5 tabs)
├── mcp/                           # ← NOT YET BUILT: Risk MCP server goes here
├── notebooks/                     # BQuant research notebook specs (01-07.md)
├── scripts/
│   ├── generate_synthetic_cache.py  # Offline demo: 5yr synthetic correlated prices
│   └── pull_drishti_data.py         # FRTL Bloomberg pull (50 equities + indices + factors)
├── data/
│   ├── samples/nifty-demo-2026.json # 12-stock sample portfolio
│   ├── csv/all nse index.csv        # Bloomberg NSE index ticker reference
│   ├── mappings/                    # bloomberg_tickers.json, sector_map.json
│   └── cache/
│       ├── bloomberg/               # Real Bloomberg parquet files (gitignored)
│       │   ├── equities/            # HDFCB_IN_Equity.parquet etc (PX_LAST + PX_VOLUME)
│       │   ├── equities/*_annual.parquet  # Annual fundamentals (ROE, debt, etc.)
│       │   ├── indices/             # NSENRG, NSEMET, NSEFMCG, NSEIT, NSEBANK, etc.
│       │   ├── commodities/         # CO1, CL1, GC1, HG1, NG1, S 1, W 1
│       │   └── macro/               # USDINR, GIND10YR, INVIXN
│       └── research_artifacts/      # Exported from BQuant (gitignored, not yet populated)
├── tests/                           # pytest — 14 tests passing
├── requirements.txt
├── .env.example
└── README.md
```

---

## Running the project

**Local / real Bloomberg data (primary):**
```bash
cd drishti
source .venv/bin/activate
uvicorn src.dashboard.app:app --reload
# → http://localhost:8000
```
Bloomberg data is already at `data/cache/bloomberg/` — no extra steps.

**Offline / synthetic data (no Bloomberg cache):**
```bash
source .venv/bin/activate
python scripts/generate_synthetic_cache.py   # only needed once
uvicorn src.dashboard.app:app --reload
```

**At FRTL (Bloomberg terminal machine) — data pull:**
```bat
cd C:\Users\User\Pranav\drishti
.venv\Scripts\activate
python scripts\pull_drishti_data.py --validate          # test fields first
python scripts\pull_drishti_data.py --skip-equities     # fast first pass (~5 min)
python scripts\pull_drishti_data.py                     # full pull (~60 min)
```
Copy `data\cache\bloomberg\` to Mac at `drishti/data/cache/bloomberg/` after pull.

**Tests:**
```bash
PYTHONPATH=. pytest tests/ -v
```

---

## Bloomberg data pull — known issues and fixes

All resolved as of 2026-06-01:

| Issue | Fix |
|-------|-----|
| `PX_ADJ_CLOSE` all null | FRTL entitlement issue. Use `PX_LAST` with `adj_split=True` + `adj_normal=True` — gives adjusted prices. |
| 15 equity tickers invalid | Bloomberg uses shorter codes, not NSE symbols. All corrected (e.g. `HDFCB`, `INFO`, `KMB`, `HUVR`). |
| `NSEOILGS`, `NSEMETAL` invalid | Those tickers don't exist. Correct codes: `NSENRG Index`, `NSEMET Index`. |
| `NSEPBKIDX` invalid | Correct code: `NSEPSBK Index`. |
| `GIND10YR` / `INVIXN` going to `indices/` | Fixed `cache_path_for()` — checks specific macro tickers before generic INDEX rule. |
| BDP pre-validation false negatives | FRTL BDP returns partial responses for large batches. Removed pre-validation; BDH handles errors directly. |

**Confirmed working Bloomberg equity codes (NSE → Bloomberg):**
```
HDFCBANK → HDFCB    INFY     → INFO     ICICIBANK → ICICIBC
KOTAKBANK → KMB     BAJFIN   → BAF      HINDUNILVR → HUVR
HCLTECH  → HCLT     WIPRO    → WPRO     NESTLEIND  → NEST
ASIANPAINT → APNT   TATAMOTORS → TTMT   HINDALCO   → HNDL
POWERGRID → PWGR    TATASTEEL → TATA    TITAN      → TTAN
MARUTI   → MSIL
```
All others match NSE symbol directly (e.g. RELIANCE, TCS, SBIN, ONGC, ITC, LT, NTPC).

---

## Key design decisions

### VaR — three genuinely different methods
1. **Historical** — empirical quantile; multi-day uses non-overlapping windows (not √t, which contradicts the clustering thesis).
2. **Parametric (delta-normal)** — multivariate-normal assumption; √t horizon scaling stated as an assumption in output.
3. **GARCH-FHS** — GARCH(1,1) standardizes residuals, bootstraps from them using GARCH-forecasted vol. Preserves empirical tail shape. Genuinely different from parametric.

### IC — time-series, not cross-sectional scalar
A commodity return at time t is a scalar identical for all stocks — cross-sectional IC is undefined. IC = rolling Pearson correlation between `factor_{t-lag}` and `target_t` over 63-day windows. This is the correct specification.

### HMM canonical labeling
After every walk-forward refit, states are relabeled by emission mean of rolling-vol feature (state 0 = low-vol, state 1 = high-vol). Prevents label-switching across monthly refits.

### Benjamini-Hochberg FDR correction
~200+ factor × sector × lag tests. BH correction at α=0.05 applied to all IC p-values. `bh_significant` flag in `ICResult` is the one to use for reporting.

### Diebold-Yilmaz
Pesaran-Shin generalized FEVD — order-invariant (unlike Cholesky). VAR lag by AIC, capped at 5. Total connectedness = % of forecast-error variance from cross-market shocks.

### Copilot safety
LLM receives only the structured risk memo — never raw holdings or prices. buy/sell/hold/invest/recommend → refused, redirected to risk diagnostics.

---

## Bloomberg data policy

`data/cache/bloomberg/` is gitignored. Never commit parquet files. Cite "Bloomberg Terminal, FRTL, IIM Calcutta" in all research outputs and the dashboard memo.

---

## Code conventions

- Pure functions in `src/risk/` and `src/research/` — no side effects, no API calls.
- All risk functions return typed dataclasses from `src/models.py`.
- Routes in `src/dashboard/routes/` are thin: call service functions, return JSON.
- Bloomberg tickers in full format: `"HDFCB IN Equity"`, `"CO1 Comdty"`, `"NSENRG Index"`.
- Comments only for non-obvious WHY — never what the code does.
- No investment advice language anywhere in generated output.
