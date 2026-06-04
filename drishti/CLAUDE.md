# Drishti — Claude Code Context

## What this project is

Drishti is a local-first quant risk research platform for Indian equity portfolios, built as a Financial Risk Management course project at IIM Calcutta (PGDBA Sem 3). It imports a Zerodha portfolio, pulls Bloomberg data, computes market risk, researches commodity factor signals, detects volatility regimes, and exposes everything through a web dashboard and an MCP-grounded AI copilot.

**This is a course demo prototype, not a production system.** All language must be educational and diagnostic — never investment advice.

---

## Current status (as of 2026-06-04)

**Track A — Frontend overhaul: COMPLETE ✅** Branch `feature/frontend-data-overhaul`.
Track B (data layer) in progress.

### Active branch
`feature/frontend-data-overhaul` — all work for the overhaul goes here. PR to `main` when done.

### Design spec (read this before touching anything in this branch)
`docs/superpowers/specs/2026-06-03-drishti-frontend-data-overhaul-design.md`

### Frontend code guide (read before any frontend work — saves token context)
`docs/frontend/code.md` — **exists — read before any frontend work**

### For all frontend changes
1. Read `docs/frontend/code.md` first (now exists — always read before any frontend work)
2. CSS variables live in `src/dashboard/static/css/theme.css` (once split)
3. JS functions are split across `src/dashboard/static/js/*.js` (once split)
4. HTML templates live in `src/dashboard/templates/` (once migrated)

---

**Session 2 complete.** Dashboard frontend fully redesigned and a 6-preset multi-theme system added.

### What's working end-to-end
- ✅ Bloomberg data pipeline (FRTL → parquet cache → dashboard)
- ✅ Portfolio import (sample, CSV, Zerodha)
- ✅ All three VaR methods (historical non-overlapping, parametric, GARCH-FHS)
- ✅ ES, Kupiec + Christoffersen backtest, component VaR, drawdown, stress scenarios
- ✅ HMM 2-state regime detection + regime-conditioned VaR
- ✅ DCC-GARCH dynamic correlations (2-step Engle estimator)
- ✅ Diebold-Yilmaz connectedness (VAR + Pesaran-Shin GFEVD)
- ✅ Time-series IC + Granger causality + BH FDR correction
- ✅ Deterministic risk memo (no LLM required)
- ✅ FastAPI backend + Plotly.js single-page dashboard (5 tabs)
- ✅ 14 unit tests passing
- ✅ `pull_drishti_data.py` — production Bloomberg pull script (tqdm, resumable, --validate)
- ✅ 7 BQuant research notebook specs (`notebooks/01-07.md`)
- ✅ `lessons.md` — all FRTL/methodology/engineering learnings documented
- ✅ **Dashboard dark theme redesign** — Playfair Display + DM Sans + JetBrains Mono; deep navy-black bg (#07090E), gold accent (#C9A227); all Plotly charts updated to dark palette
- ✅ **Multi-theme system** — 6 presets × 8 accent swatches; ⬡ icon button in header opens popover picker; CSS variable injection (zero reload); localStorage persistence
- ✅ **JS showTab bug fixed** — regime and IC data now load lazily via `_regimeLoaded` / `_icLoaded` flags, not on every tab switch
- ✅ **Jinja2 template migration** — base.html + index.html + learn.html; CSS/JS split into 16 files; tooltip system; /api/static-data endpoint
- ✅ **`/learn` knowledge page** — methodology (KaTeX), glossary, broker guides, findings placeholder

### What's left to build
| Priority | Item | File | Notes |
|----------|------|------|-------|
| 🔴 High | **Walk-forward OOS Sharpe** | `src/research/walk_forward.py` + route `/api/research/walkforward` | Spec in `notebooks/05_walk_forward_backtest.md`. Rolling 252-day train, monthly OOS Sharpe per factor-sector pair. |
| 🔴 High | **Risk MCP server** | `mcp/server.py` + `mcp/tools.py` | All analytics as MCP tools. Tools: `calculate_portfolio_risk`, `get_var_backtest`, `get_current_regime`, `get_factor_signals`, `run_stress_test`, `generate_risk_memo`. |
| 🟡 Medium | **Rolling Diebold-Yilmaz route** | New route in `src/dashboard/routes/research.py` | `rolling_spillover()` already in `src/research/diebold_yilmaz.py`. Just needs `/api/research/spillover/rolling` endpoint + dashboard chart. |
| 🟢 Low | **News RSS + FinBERT** | `src/research/news.py` | Cogencis/SEBI RSS + FinBERT sentiment. Lower priority — not needed for core demo. |
| 🟢 Low | **XGBoost VaR breach classifier** | `src/research/breach_classifier.py` | Optional ML stretch goal. 1% tail events → severe class imbalance, needs SMOTE. |

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
├── lessons.md                       # FRTL Bloomberg learnings, methodology fixes, engineering patterns
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

## Dashboard theme system (added 2026-06-03)

All theme logic lives entirely inside `src/dashboard/static/index.html` — no separate files.

### Presets (6)
| ID | Name | Background | Default accent |
|---|---|---|---|
| `dark-gold` | Dark Gold | `#07090E` | gold |
| `dark-ocean` | Dark Ocean | `#080D18` | ocean |
| `dark-emerald` | Dark Emerald | `#07100C` | emerald |
| `dark-crimson` | Dark Crimson | `#100808` | crimson |
| `dark-violet` | Dark Violet | `#0D0814` | violet |
| `light-ivory` | Light Ivory | `#F8F5EE` | gold (dark variant) |

### Accent swatches (8)
`gold` (#C9A227) · `ocean` (#3891F0) · `emerald` (#34C76C) · `crimson` (#DC4040) · `violet` (#8B5CF6) · `teal` (#2EC4B6) · `amber` (#F59E0B) · `rose` (#EC4899)

`light-ivory` uses darkened accent variants (`ivoryHex`) for contrast on the warm-white background.

### How it works
- `applyTheme(presetId, accentId)` injects CSS variables onto `:root` via `style.setProperty()` — zero page reload.
- Sets `--bg`, `--surface`, `--surface-2`, `--ink`, `--ink-2`, `--muted`, `--line`, `--line-2`, `--ok`, `--warn`, `--danger` from the preset, then `--primary`, `--primary-light`, `--primary-dim` from the accent.
- `rethemeCharts()` calls `Plotly.relayout()` on all 6 chart divs to update `plot_bgcolor` and `font.color`.
- `initTheme()` runs on page load — reads `localStorage.getItem('drishti-theme')`, falls back to `{presetId:'dark-gold', accentId:'gold'}`.
- Every `applyTheme()` call saves `{presetId, accentId}` to `localStorage` under key `'drishti-theme'`.

### Picker UI
- `⬡` button in header right-side, next to regime badge.
- Click toggles `<div id="theme-popover">` (`display:none` / `display:block`).
- Popover contains: 3×2 grid of preset cards (`#tp-presets`) + 8 accent dots (`#tp-accents`), both rendered by `renderThemePicker()`.
- Closes on click-outside (`mousedown` on `document`) or Escape key.

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

---

## Overhaul context (Session 3 — branch feature/frontend-data-overhaul)

### What is being built (two independent tracks)

**Track A — Frontend overhaul:**
- Migrate from single `src/dashboard/static/index.html` (1059 lines) to Jinja2 templates
- New directory: `src/dashboard/templates/` with `base.html`, `index.html`, `learn.html`
- New directory: `src/dashboard/static/css/` with `theme.css`, `layout.css`, `components.css`, `tooltip.css`
- New directory: `src/dashboard/static/js/` with `theme.js`, `api.js`, `charts.js`, `portfolio.js`, `risk.js`, `research.js`, `spillover.js`, `copilot.js`, `tooltip.js`
- New file: `src/dashboard/static/data/glossary.json` — tooltip content, served at `/static/data/glossary.json`
- New route: `src/dashboard/routes/static_data.py` → `/api/static-data`
- New page: `/learn` — Know/Learn page with methodology, broker guides, glossary, findings
- `app.py` gets: `StaticFiles` mount at `/static`, `Jinja2Templates`, `/learn` route
- `docs/frontend/code.md` — structure guide (Claude reads before any frontend work)

**Track B — Data layer:**
- New script: `scripts/pull_public_data.py` — yfinance + FRED gap-fill from last Bloomberg date (2026-05-29) onwards
- New file: `data/mappings/yahoo_tickers.json` — Bloomberg ticker → Yahoo Finance ticker map
- Updated: `src/bloomberg/cache.py` — add `read_merged()` method (Bloomberg rows win on overlap)
- New: `requirements.txt` gets `yfinance` and `fredapi`
- New: `.env.example` gets `FRED_API_KEY`
- New: `.github/workflows/weekly.yml` — Sunday 2 AM UTC: synthetic refresh + pytest + Render deploy
- New: `render.yaml` at repo root — Render.com deploy config

### Critical facts about the current app.py
- Currently serves `index.html` via raw `HTMLResponse(file.read_text())` — NO StaticFiles mount
- This means any CSS/JS in `static/` will 404 until `app.mount("/static", StaticFiles(...))` is added
- `Jinja2` (3.1.4) is already in `requirements.txt` — no new dependency needed
- `/learn` route does not exist yet — will 404 until added

### Current Bloomberg data
- Date range: 2018-01-01 → 2026-05-29 (essentially current, ~5 days stale)
- 49 NSE equities (daily + annual fundamentals), 15 indices, 7 commodities, 3 macro series
- Parquets are gitignored — never commit them
- Annual fundamentals: 8 fields — RETURN_COM_EQY, BS_TOT_ASSET, NET_INCOME, SHORT_AND_LONG_TERM_DEBT, BOOK_VAL_PER_SH, EQY_DPS, CF_CASH_FROM_OPER, EQY_SH_OUT

### JS load order (strict — do not reorder)
Plotly CDN → theme.js → api.js → charts.js → portfolio.js → risk.js → research.js → spillover.js → copilot.js → tooltip.js

### CSS load order (strict)
theme.css → layout.css → components.css → tooltip.css

### JS global scope contracts
- `window.API = ""` declared in `api.js` — all other files use `window.API`
- `riskData`, `_regimeLoaded`, `_icLoaded` declared in `portfolio.js` — global state
- `CL`, `CONF`, `COLORS` declared in `charts.js` — Plotly config shared by all tab files
- `PRESETS`, `ACCENTS`, `_theme` declared in `theme.js`
- `initTheme()` called immediately at bottom of `theme.js` — only immediate execution in any JS file

### Tooltip system
- `data-tip="key"` attribute on any HTML element
- `tooltip.js` loads `glossary.json` on DOMContentLoaded, attaches mouseenter/mouseleave to all `[data-tip]` elements
- Single shared popover div, positioned via getBoundingClientRect
- "Read more →" links to `/learn#glossary`

### Data strategy
- Bloomberg parquets (2018→2026-05-29): immutable backbone, never overwritten
- Public cache (`data/cache/public/`): yfinance + FRED gap-fill, committed to repo (not gitignored)
- `read_merged()` in cache.py: reads both, concatenates, Bloomberg rows win on overlap
- `pull_public_data.py`: reads last date from parquet, fetches only the gap, appends to public cache
