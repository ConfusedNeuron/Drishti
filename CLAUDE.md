# Drishti — Claude Code Context

## What this project is

Drishti is a local-first quant risk research platform for Indian equity portfolios, built as a Financial Risk Management course project at IIM Calcutta (PGDBA Sem 3). It imports a Zerodha portfolio, pulls Bloomberg data, computes market risk, researches commodity factor signals, detects volatility regimes, and exposes everything through a web dashboard and an MCP-grounded AI copilot.

**This is a course demo prototype, not a production system.** All language must be educational and diagnostic — never investment advice.

---

## Current status (as of 2026-06-14)

**Track A — Frontend overhaul: COMPLETE ✅**
**Track B — Data layer: COMPLETE ✅**
**Track C — Walk-forward + MCP + Rolling DY: COMPLETE ✅**
**Track D — News+FinBERT + XGBoost breach classifier: COMPLETE ✅**
**Track E — Frontend UX fixes: COMPLETE ✅**
**Track F — v2 Expansion: COMPLETE ✅**
**Track G — v3 Findings Notebooks: COMPLETE ✅** (pending merge of PR #10)

### Active branch
`feature/v3-findings-notebooks` — v3 phase-1 (course-grounded findings notebooks + analytics helpers). Open PR: #10.

### Track G — v3 status (as of 2026-06-14)
Executed subagent-driven (validator → implementer → reviewer per task; validator caught real defects on 6 tasks). All on `feature/v3-findings-notebooks`.

**DONE & committed (all reviewed, tests green, notebooks run headless):**
- ✅ `scripts/run_notebook_md.py` — notebook `[CODE]`-cell execution harness
- ✅ `scripts/pull_ohlc_frtl.py` — OHLC pull for v2 universe (extreme-value vol)
- ✅ `src/research/series_io.py` — v2 index/commodity/macro/OHLC loaders
- ✅ `src/risk/performance.py` (Sharpe/Treynor/Jensen), `src/risk/ewma.py`, `src/risk/evt.py` (POT/GPD), `src/risk/extreme_value_vol.py` (Parkinson/GK/RS)
- ✅ `src/portfolio/frontier.py` (Markowitz), `src/research/tar.py` (TAR + bootstrap test), `src/research/cointegration.py` (Johansen/VECM), `src/research/credit.py` (Altman), `src/research/liquidity.py` (Amihud)
- ✅ Notebooks `08`–`15` (growth, risk/perf, covariance, frontier, TAR regime, advanced Box-Jenkins/GARCH ×17 series, spillover/connectedness, credit/liquidity) — all run headless, all reviewed
- ✅ `notebooks/README.md` syllabus-coverage matrix; `docs/methodology.html` extended to 39 sections; README v3 section
- ✅ Test suite: **163 passing** (122 baseline + 41 new); all 8 notebooks verified headless

**REMAINING:**
- ✅ OHLC pulled at FRTL and copied to `data/cache/bloomberg_v2/ohlc/` (29 indices + 433 equities + 15 commodities, ~2000→2026, gitignored) — notebook 13 range-based volatility (Parkinson/GK/RS) now computes live (NIFTY ≈ 0.19 annualized)
- 🔲 Merge PR #10 → main (in progress)

### Previous active branch
`feature/v2-expansion` — merged to main (PR #8)

### Pre-demo checklist (presentation: 2026-06-16 Mon)
- [ ] `pip install transformers torch` — required for FinBERT sentiment panel (~2 GB, one-time)
- [ ] `pip install imbalanced-learn` — only needed if retraining breach classifier
- [ ] Commit `docs/methodology.html` + `data/cache/research_artifacts_v2/` + `scripts/pull_drishti_v2_fallback.py`
- [ ] Merge `feature/v2-expansion` → `main`

### Frontend code guide (read before any frontend work — saves token context)
`docs/frontend/code.md` — **exists — read before any frontend work**

### For all frontend changes
1. Read `docs/frontend/code.md` first (always read before any frontend work)
2. CSS variables live in `src/dashboard/static/css/theme.css`
3. JS functions are split across `src/dashboard/static/js/*.js`
4. HTML templates live in `src/dashboard/templates/`

---

**Session 5 complete.** Frontend UX fixes: tooltip hover-bridge, theme picker (overflow:hidden bug + render-on-open), `/learn` page linked from header, section subtitles + chart reading notes across all tabs, hardcoded colors replaced with CSS variables.

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
- ✅ 122 unit tests passing
- ✅ `pull_drishti_data.py` — production Bloomberg pull script (tqdm, resumable, --validate)
- ✅ 7 BQuant research notebook specs (`notebooks/01-07.md`)
- ✅ `lessons.md` — all FRTL/methodology/engineering learnings documented
- ✅ **Dashboard dark theme redesign** — Playfair Display + DM Sans + JetBrains Mono; deep navy-black bg (#07090E), gold accent (#C9A227); all Plotly charts updated to dark palette
- ✅ **Multi-theme system** — 6 presets × 8 accent swatches; "⬡ Theme" labeled button in header opens popover picker; CSS variable injection (zero reload); localStorage persistence
- ✅ **Theme picker fixed** — `overflow:hidden` on header was clipping the popover; `renderThemePicker()` now called on open not just at page load; all hardcoded colors (`header h1`, `nav` background, gradient mid-stop) replaced with CSS variables
- ✅ **JS showTab bug fixed** — regime and IC data now load lazily via `_regimeLoaded` / `_icLoaded` flags, not on every tab switch
- ✅ **Jinja2 template migration** — base.html + index.html + learn.html; CSS/JS split into 16 files; tooltip system; /api/static-data endpoint
- ✅ **`/learn` knowledge page** — methodology (KaTeX), glossary, broker guides, findings placeholder; linked from shared header "Learn" pill; "Drishti" logo links home
- ✅ **Tooltip "Read more" fixed** — removed `pointer-events:none`; 180ms hover-bridge so cursor can reach the link without the popover closing
- ✅ **Panel explainers** — `.section-sub` subtitle + `.chart-note` "↳ How to read" note on every section and chart across all 5 tabs
- ✅ **Walk-forward OOS Sharpe** — `src/research/walk_forward.py`; rolling 252-day train / monthly OOS step; IC-guided pair selection with BH-fallback; Plotly heatmap (factor × sector) in Research tab
- ✅ **Risk MCP server** — `risk_mcp/server.py` + `risk_mcp/tools.py`; 6 tools wrapping existing analytics; word-boundary safety filter blocks investment-advice prompts; boots via `python risk_mcp/server.py`
- ✅ **Rolling Diebold-Yilmaz** — `/api/research/spillover/rolling` route; wires pre-existing `rolling_spillover()`; filled-area connectedness chart auto-loads in Spillover tab
- ✅ **News RSS + FinBERT** — `src/research/news.py`; 5 Indian finance RSS sources; `ProsusAI/finbert` sentiment scoring; file-cached (`data/cache/news/latest.json`); Refresh button in Research tab; sentiment injected into risk memo; module-level pipeline cache avoids reload cost
- ✅ **XGBoost VaR breach classifier** — `src/research/breach_classifier.py` + `scripts/train_breach_classifier.py`; next-day breach probability (no look-ahead — target uses `r.shift(-1)`); SMOTE applied after train/test split; commodity lags (`brent_lag1`, `gold_lag1`, `copper_lag1`) + regime + rolling vol features; breach probability gauge + feature importance chart in Research tab
- ✅ **v2 data switch** — DRISHTI_DATA_VERSION=v2 env var routes to bloomberg_v2/ and research_artifacts_v2/; v1 is still the default
- ✅ **Diagnostics ladder** — ADF → Ljung-Box → ARCH-LM → GARCH order scan (BIC table) → Engle-Sheppard CCC test; GET /api/research/diagnostics
- ✅ **ADCC** — asymmetric DCC (Cappiello-Engle-Sheppard 2006); fit_dcc_garch(..., asymmetric=True) returns gamma; grid-search fallback for optimizer failures
- ✅ **Weekly Granger** — granger_test(..., freq="weekly") compounds daily→weekly; BH-corrected over Granger table; summarize_granger_aic() picks min-AIC lag per pair
- ✅ **Universe module** — src/research/universe.py; load_universe/load_sectors/build_size_buckets/sector_composites; large=NSE100, mid=NSEMD150
- ✅ **Expanded spillover study** — scripts/build_spillover_study.py; large/mid/combined panels; IS/OOS date-split seam; writes spillover_study.json to research_artifacts_v2/
- ✅ **Market Shock Events** — src/research/events.py; detect_drawdown_episodes (≥10%); match_labels against 14-event curated map; episode_stats; statistical_levels; practitioner_appendix (heuristics, clearly separated); Events tab
- ✅ **Bull/Bear Regime study** — src/research/market_regimes.py; classify_bull_bear (20% rule); regime_signs stats table; current_state; HMM overlay; Regimes tab
- ✅ **IPO truncation fix** — filter_min_history() in returns.py; MIN_HISTORY_DAYS=756 (3yr default); prevents young IPOs from truncating the return matrix via dropna
- ✅ **Unified safety filter** — src/copilot/safety.py; word-boundary regex; shared by MCP tools and copilot route
- ✅ **News dry-run script** — scripts/news_dry_run.py; validates FinBERT download + all feeds; second run < 60s
- ✅ **pull_drishti_v2.py** — scripts/pull_drishti_v2.py; survivorship-free Nifty100+Midcap150 since 2000; INDX_MWEIGHT_HIST snapshots; resumes safely; writes to bloomberg_v2/ only
- ✅ **verify_v2_cache.py** — scripts/verify_v2_cache.py; post-pull sanity report
- ✅ **Events tab** — src/research/events.py; detect_drawdown_episodes (≥10% threshold); 16 curated labels (dot-com → 2026 tariff shock); statistical levels; practitioner appendix; GET /api/research/events; events.js + Events nav tab
- ✅ **Regimes tab** — src/research/market_regimes.py; 20% bull/bear rule; regime_signs stats table; current_state; HMM overlay; GET /api/research/regimes-study; regimes.js + Regimes nav tab
- ✅ **IS/IN Equity fallback** — cache.py read_cache() falls back from `TICKER IN Equity` → `TICKER IS Equity` filename; v2 Bloomberg pull uses IS exchange code, v1 tickers.py maps to IN; both work transparently
- ✅ **v2 Bloomberg data imported** — 433 equities (229 NSE100 + 204 NSEMD150), 29 indices, 15 commodities, 4 macro; date range ~2006–2026-06-12; loaded via DRISHTI_DATA_VERSION=v2
- ✅ **v2 research artifacts built** — data/cache/research_artifacts_v2/: spillover_study.json, events_study.json, regime_study.json (built via build_*.py scripts)
- ✅ **docs/methodology.html** — comprehensive 30-section mathematical reference; all VaR methods, ES, backtests, GARCH, HMM, DCC/ADCC, Diebold-Yilmaz, IC, Granger, BH, walk-forward, XGBoost, FinBERT; MathJax equations; dark-themed HTML matching dashboard

### What's left to build

Nothing planned for v2. Three optional REVISIT items in docs/design-choices.md (FinBERT download speed, news refresh latency, RSS reliability) — only relevant if the demo machine is slow.

**Pending before merge:** install `transformers` + `torch` for FinBERT; commit methodology.html + artifacts; merge to main.

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
<repo root>/            # flattened — formerly the drishti/ subfolder
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
│   │   ├── dcc_garch.py           # DCC-GARCH dynamic correlations (2-step Engle 2002); ADCC (Cappiello-Engle-Sheppard)
│   │   ├── diebold_yilmaz.py      # Connectedness index (VAR + Pesaran-Shin GFEVD); rolling_spillover()
│   │   ├── walk_forward.py        # Rolling 252-day OOS Sharpe per (factor × sector) pair
│   │   ├── news.py                # RSS fetch + FinBERT scoring + file cache + sentiment helpers
│   │   ├── breach_classifier.py   # XGBoost breach feature engineering + load/predict
│   │   ├── universe.py            # load_universe/load_sectors/build_size_buckets/sector_composites
│   │   ├── events.py              # detect_drawdown_episodes; match_labels; episode_stats; statistical_levels
│   │   └── market_regimes.py      # classify_bull_bear (20% rule); regime_signs; current_state; HMM overlay
│   ├── copilot/
│   │   └── memo.py                # Deterministic risk memo (no LLM required)
│   └── dashboard/
│       ├── app.py                 # FastAPI app entry point
│       ├── routes/                # portfolio / risk / research / copilot routes
│       └── static/index.html      # Single-page Plotly.js dashboard (5 tabs)
├── risk_mcp/                      # Risk MCP server (named risk_mcp/ to avoid shadowing the mcp PyPI package)
│   ├── server.py                  # FastMCP server; boot with: python risk_mcp/server.py
│   └── tools.py                   # 6 tools wrapping src/risk/ + src/research/; word-boundary safety filter
├── notebooks/                     # BQuant research notebook specs (01-07.md)
├── scripts/
│   ├── generate_synthetic_cache.py  # Offline demo: 5yr synthetic correlated prices
│   ├── pull_drishti_data.py         # FRTL Bloomberg pull v1 (50 equities + indices + factors)
│   ├── pull_drishti_v2.py           # FRTL Bloomberg pull v2 (survivorship-free Nifty100+Midcap150 since 2000)
│   ├── pull_drishti_v2_fallback.py  # Variant with INDX_MWEIGHT fallback for entitlement-limited FRTL
│   ├── verify_v2_cache.py           # Post-pull sanity report for bloomberg_v2/
│   ├── build_spillover_study.py     # Builds research_artifacts_v2/spillover_study.json
│   ├── build_events_study.py        # Builds research_artifacts_v2/events_study.json
│   ├── build_regime_study.py        # Builds research_artifacts_v2/regime_study.json
│   ├── news_dry_run.py              # Validates FinBERT download + all RSS feeds; second run < 60s
│   └── train_breach_classifier.py   # One-time XGBoost training: split→scale_pos_weight→fit→saves breach_classifier.pkl
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
│       ├── bloomberg_v2/            # v2 parquet files (gitignored — Bloomberg licensing)
│       │   ├── equities/            # 433 tickers (NSE100 + NSEMD150); PX_LAST + PX_VOLUME + PE_RATIO + P/B + mktcap
│       │   ├── indices/             # 29 indices (v1 set + NSE100/500/NSEMD150/sector additions)
│       │   ├── commodities/         # 15 commodities (v1 7 + silver/aluminium/zinc/sugar/cotton/CPO/coal/iron ore)
│       │   ├── macro/               # USDINR, GIND10YR, INVIXN, DXY
│       │   ├── ohlc/                # PX_OPEN/HIGH/LOW/LAST for indices/equities/commodities (range-vol; pull_ohlc_frtl.py)
│       │   └── meta/                # universe_v2.json, sectors_v2.json, failed_v2.json, membership snapshots
│       ├── research_artifacts/      # Exported from BQuant (gitignored, not yet populated)
│       ├── research_artifacts_v2/   # Built by build_*.py scripts (NOT gitignored — JSON, commit for demo)
│       │   ├── spillover_study.json # Diebold-Yilmaz: large/mid/combined panels; IS/OOS split
│       │   ├── events_study.json    # 16 labeled drawdown episodes; statistical levels; practitioner appendix
│       │   └── regime_study.json    # Bull/bear classifications; regime stats; HMM overlay; current state
│       ├── news/
│       │   └── latest.json          # FinBERT-scored headlines cache (created by POST /api/research/news/refresh)
│       └── models/
│           └── breach_classifier.pkl  # Trained XGBoost model (created by scripts/train_breach_classifier.py)
├── tests/                           # pytest — 122 tests passing
├── design/                          # PRD, specs, high/low-level design (HTML)
├── docs/                            # design-choices.md, lessons.md, audit-remediation-plan.md, frontend/code.md, methodology.html
├── requirements.txt
├── .env.example
├── README.md
└── CLAUDE.md
```

---

## Running the project

**Local / real Bloomberg data (primary):**
```bash
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
Copy `data\cache\bloomberg\` to Mac at `data/cache/bloomberg/` after pull.

**Risk MCP server (standalone):**
```bash
source .venv/bin/activate
python risk_mcp/server.py
```
Connect any MCP-compatible client (Claude Desktop, etc.) to this server. Six tools available: `calculate_portfolio_risk`, `get_var_backtest`, `get_current_regime`, `get_factor_signals`, `run_stress_test`, `generate_risk_memo`.

**Train XGBoost breach classifier (one-time, requires Bloomberg cache):**
```bash
source .venv/bin/activate
PYTHONPATH=. python scripts/train_breach_classifier.py
# → saves data/cache/models/breach_classifier.pkl
# → prints class distribution, AUC-PR, feature importances
```

**Refresh news sentiment (on demand, requires internet):**
```bash
# Via the dashboard: click "Refresh" in the Market Sentiment panel (Research tab)
# Or via curl:
curl -X POST http://localhost:8000/api/research/news/refresh
# → downloads ProsusAI/finbert (~440 MB on first run), scores headlines, writes data/cache/news/latest.json
```

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

## Design choices log

All significant architectural and methodology decisions with alternatives and revisit status live in:
**`docs/design-choices.md`** — read this before making any methodology or architecture call. Update it when a decision changes.

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

## Dashboard theme system (added 2026-06-03, fixed 2026-06-11)

Theme logic is split across `theme.js`, `components.css`, and `layout.css`.

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

### Known bugs fixed (do not reintroduce)
- **Do NOT add `overflow:hidden` to `header` in `layout.css`** — it clips the absolutely-positioned `#theme-popover` (only the first section label was visible). The decorative pseudo-elements use `inset:0` and don't need clipping.
- **Do NOT add `pointer-events:none` to `#tip-popover`** in `tooltip.js` — it makes the "Read more →" link unclickable.
- **Do NOT use hardcoded colours in `layout.css`** for `header h1`, `nav` background, or gradients — use CSS variables so all 6 themes work correctly.

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
- `default_dates()` lives in `src/config.py` — import from there, do not redefine locally.
- Comments only for non-obvious WHY — never what the code does.
- No investment advice language anywhere in generated output.
- MCP safety filter uses word-boundary regex (`\b`), not substring — "shortfall" and "holdings" must not be blocked.

---

## Session history

- **Session 1:** Bloomberg data pipeline, all VaR/ES/backtest/HMM/DCC/DY analytics, deterministic risk memo
- **Session 2:** Dashboard dark theme redesign, multi-theme system, Jinja2 migration, `/learn` page, Track B data layer (yfinance gap-fill, CI/CD, Render deploy)
- **Session 3:** Walk-forward OOS Sharpe, Risk MCP server (6 tools), rolling DY chart, 28 tests
- **Session 4:** News RSS + FinBERT sentiment panel, XGBoost VaR breach classifier (next-day, no look-ahead, SMOTE after split), design-choices.md log, 69 tests
- **Session 5:** Frontend UX fixes — tooltip hover-bridge, theme picker (`overflow:hidden` + render-on-open + hardcoded colour bugs), `/learn` header link, section subtitles + chart reading notes, 81 tests
- **Session 6:** v2 expansion — ADCC, diagnostics ladder, weekly Granger, universe module, expanded spillover study, market shock events, bull/bear regimes, IPO truncation fix, unified safety filter, news dry-run, pull_drishti_v2.py + verify_v2_cache.py, v2 data version switch, 122 tests
- **Session 7:** v2 data import (433 equities, 29 indices, 15 commodities), v2 artifact builds (spillover/events/regime), IS/IN Equity cache fallback fix, 2 new event labels (FII outflow 2024 + tariff shock 2026), Events + Regimes frontend tabs, docs/methodology.html (30-section math reference)
- **Session 8:** v3 findings notebooks (PR #10) — 9 tested analytics helpers (performance ratios, EWMA, EVT-VaR, range volatility, Markowitz frontier, TAR, Johansen/VECM, Altman, Amihud), notebook execution harness, OHLC pull script, notebooks 08–15 (all run headless + reviewed), notebooks/README coverage matrix. Subagent-driven (validator→implementer→reviewer; validator caught 6 real defects). 163 tests. docs/methodology.html extended to 39 sections; README v3 section. Remaining: OHLC pull at FRTL + merge PR #10.

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
- 50 NSE equities (daily + annual fundamentals), 15 indices, 7 commodities, 3 macro series
- Parquets are gitignored — never commit them
- Annual fundamentals: 8 fields — RETURN_COM_EQY, BS_TOT_ASSET, NET_INCOME, SHORT_AND_LONG_TERM_DEBT, BOOK_VAL_PER_SH, EQY_DPS, CF_CASH_FROM_OPER, EQY_SH_OUT

### JS load order (strict — do not reorder)
Plotly CDN → theme.js → api.js → charts.js → portfolio.js → risk.js → research.js → spillover.js → events.js → regimes.js → copilot.js → tooltip.js

### CSS load order (strict)
theme.css → layout.css → components.css → tooltip.css

### JS global scope contracts
- `window.API = ""` declared in `api.js` — all other files use `window.API`
- `riskData`, `_regimeLoaded`, `_icLoaded`, `_newsLoaded`, `_breachLoaded`, `_eventsLoaded`, `_regimesStudyLoaded` declared in `portfolio.js` — global state; all flags set inside the async success path of their respective load functions (never synchronously)
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

**Track B — Data layer: COMPLETE ✅**

### Public data gap-fill architecture
- `data/mappings/yahoo_tickers.json` — Bloomberg → Yahoo Finance ticker map (4 categories)
- `scripts/pull_public_data.py` — gap-fill script; reads Bloomberg last date, fetches yfinance + FRED gap
- `src/bloomberg/cache.py:read_merged()` — transparent merge of Bloomberg + public cache (Bloomberg wins)
- `data/cache/public/` — committed to repo (not gitignored); yfinance + FRED rows only

### CI/CD and deployment
- `.github/workflows/weekly.yml` — Sunday 2 AM UTC: synthetic refresh + public pull + pytest + Render deploy
- `render.yaml` at repo root — free tier Render.com web service (spins down after 15 min idle)
- Secrets needed in GitHub repo settings: `FRED_API_KEY`, `RENDER_DEPLOY_HOOK`
- On Render dashboard: set `FRED_API_KEY` environment variable manually
