# Drishti Audit — 2026-06-15 (v1/v2 unification + correctness)

Full-repo read-through. Goal: **delete `DRISHTI_DATA_VERSION`, move everything to the
v2 data source (`bloomberg_v2/` + `research_artifacts_v2/`), and fix all issues below.**
163/163 tests pass at audit time.

## Ground truth
- v1 cache `bloomberg/`: 98 equity parquets (~49 modeled after `MIN_HISTORY_DAYS=756`), 50 annual, 15 indices, 7 commodities.
- v2 cache `bloomberg_v2/`: 433 equities, **432 `equities_annual/`** (8 fields), 29 indices, 15 commodities, 4 macro, full **OHLC** (29 idx + 433 eq + 15 cmd), `meta/{universe_v2,sectors_v2}.json`.
- v2 equity daily cols: `PX_LAST, PX_VOLUME, PE_RATIO, PX_TO_BOOK_RATIO, CUR_MKT_CAP`.
- Default version is **v1** (`config.py:8`). Sample portfolio (12 names) resolves in v2 via IN→IS fallback (`cache.py:51`). OHLC read by `series_io.load_ohlc` (always v2, hardcoded).
- v2 has everything v1 had → **moving fully to v2 loses nothing.**

---

## THEME 1 — v1/v2 split (PRIMARY)
- **1.1 🔴** `routes/research.py:305,318` — `/events` & `/regimes-study` hardcode `research_artifacts_v2`, ignoring env. Default v1 run shows v2 studies in those two tabs while the rest is v1.
- **1.2 🔴** `routes/static_data.py:27` — header badge hardcodes `research_artifacts` (v1) AND reads `hmm_result/dy_result/ic_result/var_range.json` that no script ever writes → badge always null.
- **1.3 🟠** `config.py:8` — default `v1` though all notebooks/series_io/universe/artifacts target v2.
- **1.4 🟠** `series_io.py:8`, `universe.py:10,66` — `bloomberg_v2` hardcoded (always v2 regardless of env).
- **1.5 🟠** `breach_classifier.pkl` retrained on v2 but `/breach` serves under default v1 → train/serve drift.
- **1.6 🟡** `research.py:123` `/walkforward` uses env-routed `ARTIFACTS_DIR` (inconsistent w/ hardcoded siblings; artifact never exists → always live compute).
- **1.7 🟡** Live portfolio risk runs on the 12-name sample, never the 433 universe — "same universe" achievable only as a consistent *version*, not identical names.

### Full `DRISHTI_DATA_VERSION` reference surface (all must go)
- `src/config.py:8` (def), `:9,:12` (use)
- `scripts/build_events_study.py:24-29` `_require_v2()`; `build_regime_study.py:26-28`; `build_spillover_study.py:144-147`
- `routes/research.py:309,322` (error-message text)
- `tests/test_v2_switch.py` (whole file)
- notebooks `08,09,10,11,12,13,14,15` `.md` (set env) + 9 `.ipynb` + `README.md`
- `scripts/run_drishti_mac.sh` (export)
- `CLAUDE.md`

---

## THEME 2 — Orphaned / dead code
- **2.1 🟠** `build_spillover_study.py` → `spillover_study.json` (83KB) built but **never served/consumed**; uses a *different* method (equal-weight universe composites) than live `/spillover` (NSE sector indices).
- **2.2 🟡** `research.py:284` `/diagnostics` — works but no frontend caller.
- **2.3 🟡** `static_data.py:28-31` — reads 4 artifact JSONs no script produces (dead).

---

## THEME 3 — Correctness
- **3.1 🟠** `risk/stress.py:23-31` — `sector_overrides` keys (`banks/it/fmcg/energy…`) don't match GICS names on holdings (`Financials/Information Technology…`). `"banks" in "financials"`=False, `"it" in "information technology"`=False → most overrides silently never fire; substring match fragile. Stress losses understate sector shocks.
- **3.2 🟡** `risk/returns.py:119-126` — `gsec10y` diff/pct_change/overwrite round-trip is correct but fragile.
- **3.3 🟡** `research/breach_classifier.py:123-133` — `predict_breach` relies on column order vs training (currently safe, no name guard).

---

## THEME 4 — Robustness / process
- **4.1 🟠** `config.py` resolves version at import time (moot once env var deleted).
- **4.2 🟡** `static_data.py:11` — `lru_cache(maxsize=1)` caches `data_as_of` for process life; reads only one arbitrary equity.
- **4.3 🟡** `diebold_yilmaz.py:31` — `select_order(..., verbose=False)` deprecated in current statsmodels.
- **4.4 🟡** No test asserts routes honor the data source (why 1.1/1.2 slipped). Add one.

---

## Not broken (verified)
Imports OK; 163 tests pass; notebooks set env before `src` imports. Correct: 3 VaR methods, ES, Kupiec/Christoffersen, HMM canonical labels + walk-forward (no leakage), IC HAC t-stat, BH-FDR, GFEVD, breach `shift(-1)` past-only threshold, walk-forward lag-in-OOS, EVT/POT guards, Markowitz clamp, `clean_json`, safety regex. Both caches carry the sector indices + commodities the live endpoints need.
