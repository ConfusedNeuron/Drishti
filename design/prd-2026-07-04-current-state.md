# PRD — Drishti as it exists today (v3.1)

**Date:** 2026-07-04 · **Status:** Shipped (course project delivered 2026-06-16) · **Owner:** Pranav
**Companion doc:** `design/prd-2026-07-04-personal-research-platform.md` (the v4 vision)

---

## 1. What it is

Drishti is a local-first quantitative risk research platform for Indian equity portfolios. It imports a portfolio (sample JSON / CSV / Zerodha Kite API), computes market-risk analytics on a Bloomberg data cache, runs econometric research studies, and serves everything through a FastAPI + Plotly.js dashboard and an MCP server for AI-copilot grounding.

**Positioning:** educational/diagnostic research tool. It never produces investment advice; a word-boundary safety filter enforces this in the copilot and MCP paths.

## 2. Users

| User | Need |
|---|---|
| Pranav (owner) | Risk research on his own Zerodha portfolio; course deliverable; portfolio-website demo |
| Course faculty / viva panel | Evidence of methodology depth (VaR family, GARCH, spillover, regimes) |
| Portfolio-website visitors | A working deployed demo (Render free tier, synthetic data) |

## 3. Data layer

- **Bloomberg v2 cache** (`data/cache/bloomberg_v2/`, gitignored — licensing): survivorship-free Nifty 100 + Midcap 150 universe since 2000 via `INDX_MWEIGHT_HIST`; **433 equities** (PX_LAST, volume, PE, P/B, mktcap), **29 indices**, **15 commodities**, **4 macro series** (USDINR, 10y G-sec yield, India VIX, DXY), OHLC for range-based volatility. Range ≈ 2000 → 2026-06-12.
- **Public gap-fill**: yfinance + FRED (`scripts/pull_public_data.py`, `read_merged()` — Bloomberg rows win).
- **Synthetic fallback** (`scripts/generate_synthetic_cache.py`) — what the deployed demo runs on.
- **Research artifacts** (`research_artifacts_v2/`, committed JSON): spillover, events, regime studies.

## 4. Feature inventory (all working, 175 tests green)

### Portfolio
- Import: sample JSON, broker CSV, Zerodha Kite Connect (`load_zerodha` → holdings, avg price, qty).
- Valuation, weights, sector exposure.

### Market risk
- VaR ×3: historical (non-overlapping multi-day), parametric delta-normal, GARCH(1,1)-FHS.
- Expected Shortfall; Kupiec + Christoffersen backtests; component VaR; drawdown; 5 India stress scenarios with GICS sector overrides.
- XGBoost next-day VaR-breach probability (no look-ahead; commodity-lag + regime + vol features).

### Research studies
- 2-state Gaussian HMM regime detection (walk-forward, canonical labeling) + regime-conditioned VaR.
- DCC-GARCH + ADCC dynamic correlations; diagnostics ladder (ADF → Ljung-Box → ARCH-LM → BIC scan → CCC test).
- Diebold-Yilmaz connectedness (Pesaran-Shin GFEVD, order-invariant) — static, rolling, and a large/mid/combined panel study with IS/OOS split.
- Time-series IC + Granger causality (daily & weekly) with Benjamini-Hochberg FDR over ~200+ tests.
- Walk-forward OOS Sharpe per factor×sector pair.
- Market shock events study (16 labeled drawdown episodes, 2000→2026) and 20%-rule bull/bear regime study.
- News RSS + FinBERT sentiment (5 Indian finance feeds, cached).

### Analytics library (surfaced in notebooks, not yet in dashboard)
Performance ratios (Sharpe/Treynor/Jensen), EWMA vol, EVT (POT/GPD) tail VaR, range-based vol (Parkinson/GK/RS), **Markowitz efficient frontier + tangency portfolio** (`src/portfolio/frontier.py`), TAR threshold models, Johansen/VECM cointegration, Altman Z, Amihud illiquidity.

### Delivery surfaces
- **Dashboard**: 7 tabs (Portfolio, Risk, Research, Spillover, Events, Regimes, Copilot), 6-preset theme system, `/learn` methodology page, tooltips/glossary.
- **Notebooks 01–15**: BQuant specs + findings notebooks, all headless-executable.
- **Risk MCP server**: 6 tools for any MCP client.
- **Deterministic risk memo** (no LLM required).
- **Docs**: `methodology.html` (39 sections), design-choices log, lessons log.

## 5. Architecture

FRTL Bloomberg pull scripts → parquet cache → pure functions (`src/risk/`, `src/research/`) returning typed dataclasses → thin FastAPI routes → vanilla-JS + Plotly frontend. CI: weekly GitHub Action (synthetic refresh + pytest + Render deploy hook).

## 6. Constraints & policies

- Bloomberg parquets never committed; cite "Bloomberg Terminal, FRTL, IIM Calcutta".
- No investment-advice language anywhere in output.
- Local-first: heavy compute assumes the owner's machine; Render deploy is a synthetic-data demo that spins down when idle.

## 7. Known gaps (as of 2026-07-04)

1. **Dashboard audit pending** — reconcile what the UI shows vs what works; some analytics (frontier, EVT, performance ratios) exist only in notebooks.
2. Research endpoints compute on **hardcoded panels** (4 factors × 4 sectors); no user-driven inputs.
3. Zerodha import exists but there is no login flow in the UI (token must be supplied).
4. Cache ends 2026-06-12; freshness depends on FRTL visits or the public gap-fill.
5. S&P 500 sibling dataset (`../sp500_data/`) pulled but not wired to anything.
