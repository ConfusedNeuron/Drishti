# Drishti — Claude Code Context

## What this project is

Drishti is a local-first quant risk research platform for Indian equity portfolios, built as a Financial Risk Management course project at IIM Calcutta (PGDBA Sem 3). It imports a Zerodha portfolio, pulls Bloomberg data, computes market risk, researches commodity factor signals, detects volatility regimes, and exposes everything through a web dashboard and an MCP-grounded AI copilot.

**This is a course demo prototype, not a production system.** All language must be educational and diagnostic — never investment advice.

---

## Current status (as of 2026-07-04)

**Final presentation DELIVERED 2026-06-16 ✅** — market-risk + spillover narrative (see `presentation/`).
**Dashboard audit: DONE** — `docs/audit-2026-07-04-dashboard.md` (all 25 routes enumerated, endpoint-probed against the real v2 cache; MCP + optional deps inspected). Two v4-direction PRDs drafted alongside it: `design/prd-2026-07-04-current-state.md` (as-built) and `design/prd-2026-07-04-personal-research-platform.md` (proposed personal-research-platform pivot); discussion notes in `design/discussion-2026-07-04-vision-notes.md`.
**NEXT FOCUS: fix sprint executed** on branch `fix/audit-2026-07-04-sprint` (plan: `docs/superpowers/plans/2026-07-04-fix-sprint.md`, gitignored/local) — see "Fix sprint" below. After this branch merges, next decision point is **which v4 PRD direction to pursue** (see the two PRDs above). Read `docs/frontend/code.md` before any frontend work.

### Fix sprint — 2026-07-04 (branch `fix/audit-2026-07-04-sprint`)
Seven tasks (T1–T7) closing gaps found in the dashboard audit. T1–T6 are code/test fixes; T7 is this documentation pass.
- ✅ **T1 — Copilot safety without LLM key** — safety filter now runs even with no Anthropic key configured; honest `source` labels (`llm` / `deterministic_memo` / `safety_filter` / `llm_error`) surfaced as a mode badge in the Copilot tab; `anthropic` added to `requirements.txt`.
- ✅ **T2 — Header badge fixes (two independent bugs)** — (1) `/api/static-data` was dead code: Track H built the backend correctly but no JS ever called it; `portfolio.js` now fetches it on page load (`1a78844`). (2) Separately, the already-live badge (fed by `/api/risk/summary` + `/api/research/regime`) had a CSS class-name mismatch — CSS defined `.badge-low`/`.badge-high` while JS generated `badge-low_vol`/`badge-high_vol`; selectors renamed to match (`89115ff`).
- ✅ **T3 — Diagnostics ladder surfaced** — the `/api/research/diagnostics` route existed with no UI; added a Research-tab panel (`loadDiagnostics`, `_diagLoaded` flag, null-tolerant `_diagNum` renderer) + first test for the route.
- ✅ **T4 — Route-level TTL cache** — `src/dashboard/route_cache.py`; caches regime + breach endpoints keyed on `(portfolio_id, as_of)` (7.8s/6.5s cold → ~0.004s repeat); TTL only bounds memory, `as_of` reset on every import prevents stale reads.
- ✅ **T5 — MCP tools accept caller-supplied holdings** — `snapshot_from_rows()` in `src/portfolio/importer.py`; three-tier fallback (caller holdings → dashboard snapshot → sample); `portfolio_source`/`portfolio_id` labels in MCP tool outputs — enables Zerodha Kite MCP interop without going through the dashboard first.
- ✅ **T6 — Yahoo ticker map completed** — `scripts/build_yahoo_map_v2.py` + regenerated `yahoo_tickers.json` equities coverage 48 → 433 (32 hand-curated overrides preserved).
- ✅ **T7 — This documentation pass** (CLAUDE.md + `docs/frontend/code.md` truth-up).
- **Test suite: 193 passing** (175 at sprint start + 18 new).

### Sibling experiment — US S&P 500 pull (outside this repo)
`../pull_spx_data.py` (in the parent `Financial Risk Management/` folder, NOT in this repo) is a standalone US analogue of `scripts/pull_drishti_v2.py`. **Fully self-contained** — it embeds its own BLPAPI plumbing (the v2 scripts imported it from `pull_drishti_data.py`, which Track H deleted) and writes to its own `../sp500_data/` (gitignore-equivalent: never commit; same Bloomberg licensing). Survivorship-free **S&P 500 + S&P MidCap 400** via `INDX_MWEIGHT_HIST`; prices + constituents from **1990**. Flags: `--validate/--discover/--indices/--commodities/--crypto/--macro/--equities/--ohlc/--sectors/--annual/--retry-failed`. Covers GICS sector sub-indices (S5INFT…), US macro (full Treasury curve, 2s10s, HY/IG credit, VIX/VXN/SKEW/MOVE, ES1), spot gold/silver (XAU/XAG), and crypto (XBTUSD/XETUSD/BGCI, short history). Not wired into the dashboard/notebooks — purely a data-pull script for now.

**Track A — Frontend overhaul: COMPLETE ✅**
**Track B — Data layer: COMPLETE ✅**
**Track C — Walk-forward + MCP + Rolling DY: COMPLETE ✅**
**Track D — News+FinBERT + XGBoost breach classifier: COMPLETE ✅**
**Track E — Frontend UX fixes: COMPLETE ✅**
**Track F — v2 Expansion: COMPLETE ✅**
**Track G — v3 Findings Notebooks: COMPLETE ✅** (merged)
**Track H — v2 Unification + Audit Remediation: COMPLETE ✅** (merged to `main` 2026-06-15)

### Active branch
`fix/audit-2026-07-04-sprint` — the 2026-07-04 fix sprint (T1–T7, see above), not yet merged to `main`. `fix/v2-unification` (Track H) was merged 2026-06-15 (merge commit `605c729`) and the branch deleted. **Test suite: 193 passing** (was 175 before this branch). Downstream (unmerged) branches built on top since: `feature/v4-f1-zerodha` (F1 — Zerodha one-click sync + P&L) then `feature/v4-f2-frontier` (F2 — Efficient Frontier Studio) then `feature/v4-f4-spillover-lab` (F4 — Spillover Lab, the current checked-out branch, stacked on F2) — **feature/v4-f4-spillover-lab: 298 passing**. `main` has not absorbed any of these yet and still shows its own, lower count.

### Track H — v2 unification + audit remediation (2026-06-15)
Full-repo audit → subagent-driven fixes (sonnet implementers). See `docs/audit-2026-06-15-data-version.md` (findings) + `docs/audit-2026-06-15-fix-plan.md` (plan).
- ✅ **`DRISHTI_DATA_VERSION` DELETED** — the env-var data switch is gone; everything runs unconditionally on the v2 source (`bloomberg_v2/` + `research_artifacts_v2/`). `config.py` paths are unconditional; build-script `_require_v2()` guards removed; `generate_synthetic_cache.py` repointed to v2; v1-only `pull_drishti_data.py` deleted. **v1 cache archived OUT of the repo to `../drishti_v1_archive/data_cache/`** (v2 already carried daily + `equities_annual/` + full OHLC, so nothing lost).
- ✅ **Spillover study surfaced** — new `GET /api/research/spillover/study` + Spillover-tab UI (large/mid/combined KPIs, rolling line, net-spillover bars). Previously built-but-orphaned.
- ✅ **Header badge wired to v2 artifacts** (`static_data.py`) — regime from `regime_study.json`, connectedness from `spillover_study.json`. Previously read v1 JSONs that no script produced → always null.
- ✅ **Stress sector overrides fixed** (`src/risk/stress.py`) — explicit GICS↔override-key map; the old substring match (`"banks" in "financials"` = False) silently dropped every sector-specific shock.
- ✅ **Sectors normalized BICS→GICS** (`universe.load_sectors`) — `Financial`/`Technology`/`Industrial`/`Basic Materials`/… fallbacks collapse into GICS buckets (no more `Financial` vs `Financials` split).
- ✅ **Combined spillover panel now blends large+mid** (50/50 per sector, NaN-aware) instead of collapsing to large-only — combined 57.3 vs large 61.9 / mid 42.5. Artifact rebuilt.
- ✅ Minor: gsec10y diff cleanup (`returns.py`), breach feature-name guard + DataFrame training, statsmodels `verbose=` deprecation removed, obsolete `test_v2_switch.py` deleted, new route/stress/badge tests added.
- ✅ **Notebooks 08–15 re-verified headless on v2** (8/8 via `nbconvert`; deps added to `requirements.txt`).

### Track G — v3 status (as of 2026-06-14)
Executed subagent-driven (validator → implementer → reviewer per task; validator caught real defects on 6 tasks). All on `feature/v3-findings-notebooks`.

**DONE & committed (all reviewed, tests green, notebooks run headless):**
- ✅ `scripts/run_notebook_md.py` — notebook `[CODE]`-cell execution harness
- ✅ `scripts/pull_ohlc_frtl.py` — OHLC pull for v2 universe (extreme-value vol)
- ✅ `src/research/series_io.py` — v2 index/commodity/macro/OHLC loaders
- ✅ `src/risk/performance.py` (Sharpe/Treynor/Jensen), `src/risk/ewma.py`, `src/risk/evt.py` (POT/GPD), `src/risk/extreme_value_vol.py` (Parkinson/GK/RS)
- ✅ `src/portfolio/frontier.py` (Markowitz), `src/research/tar.py` (TAR + bootstrap test), `src/research/cointegration.py` (Johansen/VECM), `src/research/credit.py` (Altman), `src/research/liquidity.py` (Amihud)
- ✅ Notebooks `08`–`15` (growth, risk/perf, covariance, frontier, TAR regime, advanced Box-Jenkins/GARCH ×17 series, spillover/connectedness, credit/liquidity) — all run headless, all reviewed. **Authoritative format is `.ipynb`, executed headless via `nbconvert` on the v2 cache** (`python -m nbconvert --to notebook --execute notebooks/NN.ipynb`; needs `nbconvert`/`nbclient`/`ipykernel` + a `python3` kernelspec). The paired `08`–`15` `.md` files are readable exports **without** `## Cell [CODE]` markers, so `run_notebook_md.py` runs only the `01`–`07` spec notebooks, not these. Re-verified end-to-end on v2 2026-06-15 (8/8 pass).
- ✅ `notebooks/README.md` syllabus-coverage matrix; `docs/methodology.html` extended to 39 sections; README v3 section
- ✅ Test suite: **163 passing** (122 baseline + 41 new); all 8 notebooks verified headless

**REMAINING:**
- ✅ OHLC pulled at FRTL and copied to `data/cache/bloomberg_v2/ohlc/` (29 indices + 433 equities + 15 commodities, ~2000→2026, gitignored) — notebook 13 range-based volatility (Parkinson/GK/RS) now computes live (NIFTY ≈ 0.19 annualized)
- ✅ Merged to `main` (superseded by Track H, 2026-06-15)

### Merged branches (history)
`feature/v2-expansion` (PR #8) · `feature/v3-findings-notebooks` (PR #10, Track G) · `fix/v2-unification` (Track H, 2026-06-15) — all merged to `main` and deleted.

### Pre-demo checklist (presentation: 2026-06-16 Mon) — DELIVERED ✅ (went well)
- Deck + assets live in `presentation/` (figures, .pptx decks, `explainer.md`) — **gitignored, kept local only** (user decision 2026-07-02). See "Presentation deck" below.
- [x] Commit `docs/methodology.html` + `data/cache/research_artifacts_v2/` + `scripts/pull_drishti_v2_fallback.py` — done (all tracked).
- [x] Merge `feature/v2-expansion` → `main` — done (PR #8); Tracks G + H also merged.
- [x] Unify data on v2 — `DRISHTI_DATA_VERSION` removed; the app runs with no env var (Track H).
- [x] `pip install transformers torch` — installed in `.venv` (verified 2026-07-04); FinBERT sentiment panel dependency satisfied.
- [ ] `pip install imbalanced-learn` — optional, only if retraining the breach classifier.
- Note: notebook-execution deps (`seaborn`/`nbconvert`/`nbclient`/`ipykernel`) are in `requirements.txt`; needed only to run notebooks 08–15 live.

### Presentation deck (`presentation/`) — toolchain for regenerating
- **Numbers/figures**: all computed live from the v2 cache with the **venv python** (`.venv/bin/python` — has `pyarrow`; system python3 does NOT). Figures are matplotlib PNGs in `presentation/figures/slideNN/`, light theme (BG `#F6F3EC`, navy `#1F3A93`, gold `#B8860B`).
- **Decks**: built with **`python-pptx`** which lives in **system python3 only** (not the venv). Native shapes/tables + embedded PNGs → fully editable .pptx.
- **Previews**: `soffice --headless --convert-to pdf …` then rasterize with **`pymupdf` (installed in the venv)** — `soffice --convert-to png` only exports slide 1.
- **Content/answers**: `presentation/explainer.md` is the authoritative Q&A reference (spillover/Granger/Diebold-Yilmaz methodology, indices+commodities glossary, survivorship/synchronization, etc.).

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
- ✅ FastAPI backend + Plotly.js dashboard (7 tabs: Overview, Risk Detail, Factor Research, Spillover, Events, Regimes, Copilot)
- ✅ 298 unit tests passing on `feature/v4-f4-spillover-lab` (not yet merged to `main`, which is separately at its own, lower count)
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
- ✅ **XGBoost VaR breach classifier** — `src/research/breach_classifier.py` + `scripts/train_breach_classifier.py`; next-day breach probability (no look-ahead — target uses `r.shift(-1)`); class imbalance via `scale_pos_weight` (SMOTE evaluated and removed — see design-choices.md); commodity lags (`brent_lag1`, `gold_lag1`, `copper_lag1`) + regime + rolling vol features; breach probability gauge + feature importance chart in Research tab
- ✅ **v2 data switch** — `DRISHTI_DATA_VERSION` env var REMOVED (2026-06-15); app now runs unconditionally on the v2 data source (`bloomberg_v2/` + `research_artifacts_v2/`); v1 data archived to `../drishti_v1_archive/`
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
- ✅ **v2 Bloomberg data imported** — 433 equities (229 NSE100 + 204 NSEMD150), 29 indices, 15 commodities, 4 macro; date range ~2006–2026-06-12
- ✅ **v2 research artifacts built** — data/cache/research_artifacts_v2/: spillover_study.json, events_study.json, regime_study.json (built via build_*.py scripts)
- ✅ **docs/methodology.html** — comprehensive 30-section mathematical reference; all VaR methods, ES, backtests, GARCH, HMM, DCC/ADCC, Diebold-Yilmaz, IC, Granger, BH, walk-forward, XGBoost, FinBERT; MathJax equations; dark-themed HTML matching dashboard
- ✅ **Zerodha one-click sync + P&L** — `src/portfolio/kite_auth.py` (daily Kite login: `login_url` → callback token-exchange → same-date token cache at `data/cache/zerodha/`, gitignored, never logged); `/api/portfolio/zerodha/login|callback|token` + optional-param `import/zerodha` (explicit → cached → settings); `GET /pnl` per-holding unrealized mark-to-cache P&L. Frontend: Connect-Zerodha button + manual-token paste row + Holdings P&L panel (Overview tab); FREE Kite Connect Personal API (holdings only — prices come from the local cache by design; public/Render demo degrades to sample/CSV when keys are absent). Educational/diagnostic only.
- ✅ **Efficient Frontier Studio** (`feature/v4-f2-frontier`, not yet merged) — `src/portfolio/frontier_studio.py`: horizon-matched frequencies (6m/1y daily, 5y weekly, 10y/20y monthly), Ledoit-Wolf shrunk annualized mu/cov, coverage-aware current-portfolio projection, iid row-bootstrap P10–P90 frontier-risk band, tangency/min-variance/CML, 0.6x/1.0x/1.4x risk presets, weight-gap diagnostic; reuses `src/portfolio/frontier.py` unmodified. Routes: `GET/POST /api/frontier/{universe,compute}` (route_cache, GIND10YR rf with 0.065 fallback, 30-asset cap, unknown-candidate reporting). Frontend: new Frontier tab (`frontier.js`) — horizon pills, long-only toggle, candidate chips, Plotly chart (band/frontier/CML/tangency/minvar/presets/current-portfolio, click-to-select points), weight-gap table. The weight gap is reported as a diagnostic only, never as rebalancing guidance.
- ✅ **Spillover Lab** (`feature/v4-f4-spillover-lab`, stacked on `feature/v4-f2-frontier`, not yet merged) — user-driven Diebold-Yilmaz connectedness on any 3–12 cached series (equities/indices/commodities/macro/GICS sector composites), independent of the precomputed spillover study/routes (`/spillover`, `/spillover/rolling`, `/spillover/study` all untouched). `src/research/spillover_lab.py` — `build_catalog()` (lists pickable series per category), `resolve_series()` (aligns ids into a daily-return panel; GIND10YR uses `diff()` per the gsec10y convention, others `pct_change()`), `run_custom_spillover()` (capped compute, validates before any I/O), `CAPS` dict (`min_series=3`, `max_series=12`, `min_obs=250`). Routes in `src/dashboard/routes/research.py`: `GET /api/research/spillover/catalog` (`lru_cache(1)`, 503 if every category is empty), `POST /api/research/spillover/custom` (portfolio-independent `route_cache` key, `ValueError` → 422). Frontend: new "Spillover Lab" `.section` (`#spillover-lab`) inside the existing Spillover tab — `spillover.js` adds `loadSpilloverCatalog`, `onLabCategoryChange`, `addLabSeries`, `removeLabSeries`, `renderLabChips`, `runSpilloverLab`, `renderLabResults`, `showLabError`/`hideLabError`; `_spilloverLabLoaded` flag in `portfolio.js` (set synchronously in `showTab`, mirroring `_frontierUniverseLoaded`, so a failed catalog fetch doesn't retry-loop on re-clicking the tab). Tests: `test_spillover_lab.py`, `test_spillover_lab_route.py`, `test_spillover_lab_tab.py`. Educational/diagnostic only — no investment-advice language.

### What's left to build

Nothing planned for v2. Three optional REVISIT items in docs/design-choices.md (FinBERT download speed, news refresh latency, RSS reliability) — only relevant if the demo machine is slow.

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
│   │   ├── importer.py            # Load from sample JSON / CSV / Zerodha Kite API
│   │   └── kite_auth.py           # Kite Connect daily-login token helpers (login_url/exchange_token/save_token/load_cached_token)
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
│   │   ├── market_regimes.py      # classify_bull_bear (20% rule); regime_signs; current_state; HMM overlay
│   │   └── spillover_lab.py       # build_catalog/resolve_series/run_custom_spillover + CAPS — user-driven DY on any 3-12 cached series
│   ├── copilot/
│   │   └── memo.py                # Deterministic risk memo (no LLM required)
│   └── dashboard/
│       ├── app.py                 # FastAPI app entry point
│       ├── route_cache.py         # In-process TTL cache for expensive research endpoints (regime/breach); keyed on (portfolio_id, as_of)
│       ├── routes/                # portfolio / risk / research / copilot routes
│       ├── templates/             # Jinja2: base.html, index.html (7 tab panels), learn.html — see docs/frontend/code.md
│       └── static/                # css/ (theme/layout/components/tooltip) + js/ (per-tab files) + data/glossary.json
├── risk_mcp/                      # Risk MCP server (named risk_mcp/ to avoid shadowing the mcp PyPI package)
│   ├── server.py                  # FastMCP server; boot with: python risk_mcp/server.py
│   └── tools.py                   # 6 tools wrapping src/risk/ + src/research/; word-boundary safety filter
├── notebooks/                     # BQuant research notebook specs (01-07.md)
├── scripts/
│   ├── generate_synthetic_cache.py  # Offline demo: 5yr synthetic correlated prices
│   ├── pull_drishti_v2.py           # FRTL Bloomberg pull v2 (survivorship-free Nifty100+Midcap150 since 2000; v1 pull_drishti_data.py deleted in Track H)
│   ├── pull_ohlc_frtl.py            # FRTL OHLC pull for v2 universe (range-based volatility)
│   ├── pull_public_data.py          # yfinance + FRED gap-fill into data/cache/public/
│   ├── run_notebook_md.py           # Executes [CODE] cells of spec notebooks 01–07
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
├── tests/                           # pytest — 193 tests passing on `main`-bound `fix/audit-2026-07-04-sprint` (298 on feature/v4-f4-spillover-lab, not yet merged)
├── design/                          # PRD, specs, high/low-level design (HTML); prd-2026-07-04-current-state.md (as-built), prd-2026-07-04-personal-research-platform.md (proposed v4 pivot), discussion-2026-07-04-vision-notes.md
├── docs/                            # design-choices.md, lessons.md, audit-remediation-plan.md, frontend/code.md, methodology.html, audit-2026-07-04-dashboard.md
├── presentation/                    # Final FRM deck (delivered 2026-06-16; gitignored — kept local only)
│   ├── explainer.md                 # Viva/concept Q&A reference (all doubts + exam-ready answers)
│   ├── figures/slideNN/             # Light-theme matplotlib PNGs per slide (regenerable via .venv python)
│   └── pptx/                        # Native editable .pptx decks (slide4, 5to7, 8to9, 10to13b) + previews
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
python scripts\pull_drishti_v2.py --validate            # test fields first
python scripts\pull_drishti_v2.py                       # full v2 pull (resumable)
python scripts\pull_ohlc_frtl.py                        # OHLC for range-based vol
```
Copy `data\cache\bloomberg_v2\` to Mac at `data/cache/bloomberg_v2/` after pull. (v1 `pull_drishti_data.py` was deleted in Track H.)

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
- **Session 4:** News RSS + FinBERT sentiment panel, XGBoost VaR breach classifier (next-day, no look-ahead, `scale_pos_weight` for imbalance), design-choices.md log, 69 tests
- **Session 5:** Frontend UX fixes — tooltip hover-bridge, theme picker (`overflow:hidden` + render-on-open + hardcoded colour bugs), `/learn` header link, section subtitles + chart reading notes, 81 tests
- **Session 6:** v2 expansion — ADCC, diagnostics ladder, weekly Granger, universe module, expanded spillover study, market shock events, bull/bear regimes, IPO truncation fix, unified safety filter, news dry-run, pull_drishti_v2.py + verify_v2_cache.py, v2 data version switch, 122 tests
- **Session 7:** v2 data import (433 equities, 29 indices, 15 commodities), v2 artifact builds (spillover/events/regime), IS/IN Equity cache fallback fix, 2 new event labels (FII outflow 2024 + tariff shock 2026), Events + Regimes frontend tabs, docs/methodology.html (30-section math reference)
- **Session 8:** v3 findings notebooks (PR #10) — 9 tested analytics helpers (performance ratios, EWMA, EVT-VaR, range volatility, Markowitz frontier, TAR, Johansen/VECM, Altman, Amihud), notebook execution harness, OHLC pull script, notebooks 08–15 (all run headless + reviewed), notebooks/README coverage matrix. Subagent-driven (validator→implementer→reviewer; validator caught 6 real defects). 163 tests. docs/methodology.html extended to 39 sections; README v3 section. Remaining: OHLC pull at FRTL + merge PR #10.
- **Session 9:** v2 unification + audit remediation (Track H) — full-repo audit, then **deleted the `DRISHTI_DATA_VERSION` env var** and pinned everything to the v2 source (v1 cache archived to `../drishti_v1_archive/`); **surfaced the orphaned spillover study** (route + Spillover-tab UI); **wired the header badge to v2 artifacts**; fixed the **stress GICS sector-override mapping** (overrides were silently never firing); **normalized Bloomberg BICS→GICS sectors** (no more `Financial` vs `Financials`); **blended large+mid in the combined spillover panel** (was collapsing to large-only); gsec10y/breach-feature-name/statsmodels-deprecation cleanups. Subagent-driven (6 sonnet implementers, disjoint file ownership). Notebooks 08–15 re-verified headless on v2 via `nbconvert`. **175 tests.** Merged to `main` (`605c729`); branch deleted. Audit docs: `docs/audit-2026-06-15-*.md`.
- **Session 10 (2026-07-02):** US extension spike — built `../pull_spx_data.py` (parent folder, **outside this repo**), a standalone Bloomberg pull mirroring `pull_drishti_v2.py` for the US market. Survivorship-free **S&P 500 + S&P MidCap 400** via `INDX_MWEIGHT_HIST`, prices + constituents from **1990**; embeds its own BLPAPI plumbing (Track H had deleted the shared `pull_drishti_data.py`); writes to its own `../sp500_data/`. Adds OHLC, spot gold/silver (XAU/XAG), crypto (XBTUSD/XETUSD/BGCI), GICS sector sub-indices, and US macro (full Treasury curve, 2s10s, HY/IG credit, VIX/VXN/SKEW/MOVE, ES1). Not wired into the dashboard/notebooks — data-pull only. See "Sibling experiment" note under Current status.
- **Session 11 (2026-07-04):** Dashboard audit + fix sprint + v4 direction-setting. Wrote two v4 PRDs (`design/prd-2026-07-04-current-state.md` as-built, `design/prd-2026-07-04-personal-research-platform.md` proposed pivot) and discussion notes (`design/discussion-2026-07-04-vision-notes.md`); ran a full dashboard audit — enumerated all 25 routes, endpoint-probed all 19 against the real v2 cache, cross-referenced every `/api/` call in templates/JS, inspected MCP + optional-dep plumbing (`docs/audit-2026-07-04-dashboard.md`). Executed a 7-task fix sprint on `fix/audit-2026-07-04-sprint` (plan: `docs/superpowers/plans/2026-07-04-fix-sprint.md`, gitignored): **T1** copilot safety filter runs without an LLM key + honest source labels (`llm`/`deterministic_memo`/`safety_filter`/`llm_error`) + mode badge; **T2** header badge now loads from `/api/static-data` on page load + live-badge CSS class fix (`badge-low_vol`/`badge-high_vol`); **T3** diagnostics ladder surfaced in the Research tab (route existed, no UI); **T4** `src/dashboard/route_cache.py` TTL cache on regime + breach endpoints (7.8s/6.5s → ~0.004s repeat); **T5** MCP tools accept caller-supplied holdings (`snapshot_from_rows()`, three-tier fallback, portfolio source/id labels) — enables Zerodha Kite MCP interop; **T6** Yahoo ticker map completed 48 → 433 equities (`scripts/build_yahoo_map_v2.py`); **T7** this documentation truth pass. `transformers`/`torch` confirmed installed. **193 tests** (was 175). Branch not yet merged to `main`; next decision is which v4 PRD to pursue.
- **Session 12 (2026-07-06):** v4 F2 — Efficient Frontier Studio, on `feature/v4-f2-frontier` (branched from `feature/v4-f1-zerodha`, itself branched from `fix/audit-2026-07-04-sprint`; none merged to `main` yet). Subagent-driven (5 implementation tasks + reviews): `src/portfolio/frontier_studio.py` (horizon-matched frequency compounding, Ledoit-Wolf shrunk annualized mu/cov, coverage-aware portfolio projection, seeded iid row-bootstrap P10–P90 band, tangency/min-variance/CML, risk presets, weight-gap diagnostic) reusing `src/portfolio/frontier.py` unmodified; `src/dashboard/routes/frontier.py` (`GET /api/frontier/universe`, `POST /api/frontier/compute`, route_cache, GIND10YR rf w/ 0.065 fallback, 30-asset cap); new Frontier tab (`frontier.js`, between Regimes and Copilot) with horizon pills, long-only toggle, candidate chips, Plotly frontier chart with click-to-select points, and a weight-gap table (diagnostic, not rebalancing guidance). Tests: `test_frontier_studio.py`, `test_frontier_routes.py`, `test_frontier_tab.py`. **253 tests** (was 214 at branch start).
- **Session 13 (2026-07-06):** v4 F4 — Spillover Lab, on `feature/v4-f4-spillover-lab` (stacked on `feature/v4-f2-frontier`, not yet merged to `main`). First instance of the "lab" pattern (user-driven analysis on picked series, vs. the precomputed studies). Subagent-driven (4 tasks): `src/research/spillover_lab.py` (`build_catalog`/`resolve_series`/`run_custom_spillover` + `CAPS`, capped Diebold-Yilmaz on any 3–12 cached series — equities/indices/commodities/macro/sector composites); routes `GET /api/research/spillover/catalog` + `POST /api/research/spillover/custom` in `src/dashboard/routes/research.py` (portfolio-independent `route_cache`, `ValueError` → 422); "Spillover Lab" `.section` added to the existing Spillover tab (`spillover.js`: `loadSpilloverCatalog`/`onLabCategoryChange`/`addLabSeries`/`removeLabSeries`/`renderLabChips`/`runSpilloverLab`/`renderLabResults`, `_spilloverLabLoaded` flag in `portfolio.js`); one review-caught fix (pairwise heatmap axis direction was reversed — receiver/source swapped). Precomputed spillover study/routes untouched. Tests: `test_spillover_lab.py`, `test_spillover_lab_route.py`, `test_spillover_lab_tab.py`. **298 tests** (was 253 at branch start).

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
