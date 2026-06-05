# Drishti — Design Choices Log

All significant architectural and methodology decisions, with alternatives considered and revisit status.

**Status categories:**
- `CONFIRMED` — decision is final, do not second-guess
- `MAY REVISIT` — works fine now, but could be improved with more time/data
- `REVISIT` — explicitly flagged to reconsider before next release or demo

---

## Methodology

### VaR — three genuinely different methods
**Decision:** Historical (non-overlapping windows), Parametric (delta-normal, √t stated as assumption), GARCH-FHS (bootstrap from GARCH-standardised residuals).
**Alternatives considered:** Overlapping windows for historical (more obs but autocorrelated), Monte Carlo (computationally expensive, needs covariance assumption).
**Status:** `CONFIRMED`

### Multi-day historical VaR — non-overlapping windows
**Decision:** Use non-overlapping return windows instead of √t scaling for multi-day horizon.
**Rationale:** √t assumes i.i.d. returns, which contradicts the volatility clustering the HMM is designed to detect. Methodologically inconsistent to use both.
**Status:** `CONFIRMED`

### IC — time-series, not cross-sectional
**Decision:** Rolling Pearson correlation between `factor_{t-lag}` and `target_t` over 63-day windows.
**Rationale:** A single commodity return at time t is a scalar identical for all stocks — cross-sectional IC is undefined/trivially zero.
**Status:** `CONFIRMED`

### HMM — canonical labeling after every refit
**Decision:** After each walk-forward refit, relabel states by emission mean of rolling-vol feature (state 0 = low-vol, state 1 = high-vol).
**Rationale:** Prevents label-switching across monthly refits, which would make regime history incoherent.
**Status:** `CONFIRMED`

### FDR correction — Benjamini-Hochberg at α=0.05
**Decision:** BH correction across all ~200+ (factor × sector × lag) IC tests. `bh_significant` is the flag to use for reporting.
**Alternatives:** Bonferroni (too conservative at this many tests), no correction (inflated false positives).
**Status:** `CONFIRMED`

### Diebold-Yilmaz — Pesaran-Shin GFEVD
**Decision:** Order-invariant generalised FEVD. VAR lag selected by AIC, capped at 5.
**Alternatives:** Cholesky FEVD (order-dependent, arbitrary for equity returns).
**Status:** `CONFIRMED`

---

## Data

### Bloomberg price field — PX_LAST with adj flags
**Decision:** Use `PX_LAST` with `adj_split=True` + `adj_normal=True` instead of `PX_ADJ_CLOSE`.
**Rationale:** `PX_ADJ_CLOSE` returns all nulls under FRTL entitlement. Adjusted `PX_LAST` gives equivalent split/dividend-adjusted prices.
**Status:** `CONFIRMED`

### Public gap-fill — yfinance + FRED
**Decision:** `scripts/pull_public_data.py` fills the gap from last Bloomberg date onwards. `read_merged()` in cache.py merges both; Bloomberg rows win on overlap.
**Alternatives:** Alpha Vantage, Quandl (both require paid keys for Indian equities).
**Status:** `CONFIRMED`

---

## Architecture

### Walk-forward OOS Sharpe — pair selection
**Decision:** BH-significant IC pairs first; fallback to top-5 by |t-stat| if none pass BH correction.
**Rationale:** Real Bloomberg data with strict FDR often has zero BH-significant pairs; fallback prevents empty output.
**Status:** `CONFIRMED`

### MCP safety filter — word-boundary regex
**Decision:** `re.search(r'\b' + re.escape(kw) + r'\b', lower)` rather than substring matching.
**Rationale:** Substring matching blocked "shortfall" (contains "short") and "holdings" (contains "hold") — the most natural risk questions.
**Status:** `CONFIRMED`

### `default_dates()` — canonical in `src/config.py`
**Decision:** Single definition imported by all routes and `risk_mcp/tools.py`.
**Status:** `CONFIRMED`

---

## Session 4 — News + FinBERT + XGBoost (in progress)

### News sentiment model — FinBERT
**Decision:** Use `ProsusAI/finbert` via HuggingFace `transformers`. Finance-domain BERT, gives positive/negative/neutral per headline.
**Alternatives:** VADER (general-purpose lexicon, fast, no GPU needed), Loughran-McDonald dictionary (finance-specific lexicon, but rule-based), zero-shot via smaller model.
**Rationale:** FinBERT is defensible in a course context ("finance-domain pre-trained transformer") and produces probability scores, not just labels.
**Status:** `REVISIT` — if demo machine is slow or model download is painful, swap to VADER as fallback.

### News sentiment serving — file-cached, refreshed on demand
**Decision:** `/api/research/news/refresh` fetches RSS + runs FinBERT, writes `data/cache/news/latest.json`. Dashboard reads from cache. One "Refresh" button in UI.
**Alternatives:** Live inference per request (too slow, 3–8s), background asyncio task (adds lifecycle complexity), prefetch on startup (blocks boot).
**Status:** `REVISIT` — if refresh latency is too high for live demo, consider pre-scoring a static batch of headlines offline and shipping the JSON.

### News sentiment dashboard surface
**Decision:** Panel in Research tab (headline list + per-headline scores + aggregate gauge) AND one-line summary injected into the risk memo.
**Status:** `CONFIRMED`

### RSS sources
**Decision:** NSE announcements, SEBI circulars, Economic Times Markets, Mint Markets, MoneyControl. All have public RSS feeds.
**Status:** `MAY REVISIT` — if any feeds are paywalled or unreliable at demo time, drop them; ET Markets + NSE are the minimum viable set.

### XGBoost breach classifier — training approach
**Decision (current):** Pre-train via `scripts/train_breach_classifier.py`, save to `data/cache/models/breach_classifier.pkl`. App loads at startup.
**Alternatives:** Train on startup (adds 10–30s cold start), train on demand via dashboard button.
**Status:** `REVISIT` — user confirmed "try option B first, optimize later."

### XGBoost breach classifier — class imbalance
**Decision (current):** SMOTE oversampling of breach days before training.
**Alternatives:** `scale_pos_weight` in XGBoost (simpler, no extra dep), threshold tuning only (poor recall on rare events).
**Status:** `REVISIT` — revisit after seeing real breach counts on Bloomberg data; may switch to `scale_pos_weight` if SMOTE artifacts are visible.

### XGBoost breach classifier — output
**Decision:** Both (a) next-day breach probability (forward-looking) and (b) feature importance breakdown (SHAP values or native XGBoost importances).
**Status:** `CONFIRMED`

---

*Last updated: 2026-06-05*
