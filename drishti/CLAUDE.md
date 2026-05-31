# Drishti — Claude Code Context

## What this project is

Drishti is a local-first quant risk research platform for Indian equity portfolios, built as a Financial Risk Management course project at IIM Calcutta (PGDBA Sem 3). It imports a Zerodha portfolio, pulls Bloomberg data, computes market risk, researches commodity factor signals, detects volatility regimes, and exposes everything through a web dashboard and an MCP-grounded AI copilot.

**This is a course demo prototype, not a production system.** All language must be educational and diagnostic — never investment advice.

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
- **Local app** (`src/`) uses BLPAPI to pull NIFTY 50 + sector indices + commodities + macro, caches to `data/cache/bloomberg/`, and serves the dashboard.
- Both paths fall back to synthetic data (`scripts/generate_synthetic_cache.py`) for offline development.

---

## Directory layout

```
drishti/
├── src/
│   ├── config.py                  # Paths, Bloomberg ticker registry, stress scenarios
│   ├── models.py                  # Dataclasses: Holding, VaRResult, BacktestResult, etc.
│   ├── bloomberg/
│   │   ├── cache.py               # Parquet cache (read/write/freshness)
│   │   ├── client.py              # BLPAPI session + BDH/BDP; falls back to cache
│   │   └── tickers.py             # Zerodha symbol → Bloomberg ticker mapping
│   ├── portfolio/
│   │   └── importer.py            # Load from sample JSON / CSV / Zerodha Kite API
│   ├── risk/
│   │   ├── returns.py             # Return matrix builder + factor/sector series loaders
│   │   ├── var.py                 # Historical, Parametric, GARCH-FHS VaR
│   │   ├── es.py                  # Expected Shortfall
│   │   ├── backtest.py            # Kupiec LR test + Christoffersen independence test
│   │   ├── contribution.py        # Component VaR
│   │   ├── drawdown.py            # Max drawdown, current drawdown
│   │   └── stress.py              # 5 stress scenarios (COVID/rate/crude/INR/election)
│   ├── research/
│   │   ├── hmm.py                 # 2-state Gaussian HMM; walk-forward; canonical labeling
│   │   ├── ic.py                  # Time-series IC + Granger causality + BH FDR correction
│   │   ├── dcc_garch.py           # DCC-GARCH dynamic correlations (2-step Engle)
│   │   └── diebold_yilmaz.py      # Connectedness index (VAR + generalized FEVD)
│   ├── copilot/
│   │   └── memo.py                # Deterministic risk memo (no LLM required)
│   └── dashboard/
│       ├── app.py                 # FastAPI app
│       ├── routes/                # portfolio / risk / research / copilot routes
│       └── static/index.html      # Single-page Plotly.js dashboard
├── mcp/                           # Risk MCP server (not yet built)
├── notebooks/                     # BQuant research notebooks (markdown specs inside)
├── scripts/
│   ├── generate_synthetic_cache.py  # Offline demo: synthetic correlated price data
│   └── pull_bloomberg_data.py       # FRTL: pulls real Bloomberg data to parquet cache
├── data/
│   ├── samples/nifty-demo-2026.json # 12-stock sample portfolio
│   ├── mappings/                    # bloomberg_tickers.json, sector_map.json
│   └── cache/
│       ├── bloomberg/               # Parquet files per ticker (gitignored)
│       └── research_artifacts/      # Exported from BQuant notebooks (gitignored)
├── tests/                           # pytest; 14 tests passing
├── requirements.txt
├── .env.example
└── README.md
```

---

## Running the project

**Offline / synthetic data (development):**
```bash
cd drishti
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_synthetic_cache.py
uvicorn src.dashboard.app:app --reload
# → http://localhost:8000
```

**At FRTL (Bloomberg terminal machine):**
```bat
cd C:\Users\User\Pranav\drishti
.venv\Scripts\activate
python scripts/pull_bloomberg_data.py --output-dir "C:\Users\User\Pranav\drishti\data\cache\bloomberg"
```
Copy `data/cache/` to laptop before demo day.

**Tests:**
```bash
PYTHONPATH=. pytest tests/ -v
```

---

## Key design decisions

### VaR methods — three genuinely different approaches
1. **Historical simulation** — empirical quantile; multi-day uses non-overlapping windows (not √t, which contradicts the clustering thesis).
2. **Parametric (delta-normal)** — assumes multivariate-normal returns; √t horizon scaling is stated as an assumption.
3. **GARCH-FHS** — GARCH(1,1) standardizes residuals, then bootstraps from them using GARCH-forecasted volatility. Genuinely fat-tailed; differs from parametric when returns have fat tails.

### IC specification — time-series, not cross-sectional
A single commodity return (e.g. Brent at day t) is a scalar identical for all stocks — cross-sectional rank-correlation with stock returns is undefined/trivially zero. IC here is the rolling Pearson correlation between `factor_{t-lag}` and `target_t` (time-series lead-lag). This is the correct specification.

### HMM canonical labeling
After each walk-forward refit, HMM states are relabeled by emission mean of the rolling-vol feature (state 0 = lowest vol = low-vol regime). Prevents label-switching across refits.

### BH FDR correction
~200+ factor × sector × lag tests → Benjamini-Hochberg correction applied to IC p-values to control false discovery rate at 5%.

### Diebold-Yilmaz
Uses Pesaran-Shin generalized FEVD (not Cholesky), so results are order-invariant. VAR lag selected by AIC, capped at 5.

### Copilot safety
The LLM only receives the structured risk memo as context — never raw holdings or prices. Any question containing buy/sell/hold/invest keywords is rejected with a redirect to risk diagnostics.

---

## What's built

- [x] Bloomberg cache + BLPAPI client (offline fallback)
- [x] Portfolio import: Zerodha / CSV / sample
- [x] Risk engine: Historical VaR, Parametric VaR, GARCH-FHS VaR, ES
- [x] Kupiec + Christoffersen backtest
- [x] Component VaR, drawdown, stress scenarios
- [x] HMM regime detection + regime-conditioned VaR
- [x] DCC-GARCH dynamic correlations
- [x] Diebold-Yilmaz connectedness index
- [x] Time-series IC + Granger + BH correction
- [x] Deterministic risk memo
- [x] FastAPI backend + Plotly.js dashboard
- [x] Synthetic data generator
- [x] BLPAPI pull script for FRTL
- [x] 14 unit tests

## What's left

- [ ] Walk-forward OOS Sharpe for factor signals (`src/research/walk_forward.py` + route)
- [ ] Risk MCP server (`mcp/server.py` + `mcp/tools.py`)
- [ ] BQuant research notebooks (7 notebooks — markdown specs in `notebooks/`)
- [ ] Rolling Diebold-Yilmaz API route
- [ ] News RSS + FinBERT sentiment (lower priority)

---

## Bloomberg data policy

All Bloomberg data cached locally under `data/cache/bloomberg/`. Raw files are gitignored and never committed to any public repository. Cite "Bloomberg Terminal, FRTL, IIM Calcutta" in all research outputs.

---

## Code conventions

- Pure functions in `src/risk/` and `src/research/` — no side effects, no API calls.
- All risk functions return typed dataclasses from `src/models.py`.
- Routes in `src/dashboard/routes/` are thin: call service functions, return JSON.
- Bloomberg tickers always use the full Bloomberg format: `"RELIANCE IN Equity"`, `"CO1 Comdty"`.
- No comments explaining what code does — only comments explaining why (hidden constraints, non-obvious choices).
- No investment advice language anywhere in generated text.
