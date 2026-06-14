# Fix plan — v2 unification (branch `fix/v2-unification`)

Issues: see `audit-2026-06-15-data-version.md`. Decisions (user, 2026-06-15):
1. **Full purge of v1, archived to parent** — `../drishti_v1_archive/data_cache/` (DONE). Code moves fully to v2.
2. **Surface the spillover study** — new route + Spillover-tab UI.
3. **Header badge wired to v2 artifacts.**

`DRISHTI_DATA_VERSION` is deleted everywhere; `bloomberg_v2/` + `research_artifacts_v2/` become the only data source. v2 confirmed to carry everything v1 had (daily, `equities_annual/`, full OHLC).

Execution: sonnet implementer subagent per task, disjoint file ownership, sequential. Orchestrator (Opus) reviews each diff + targeted tests; full `pytest tests/` at the end.

## Tasks
- **T1 — Kill the version var (config + scripts).** `src/config.py` (drop `_DATA_VERSION`; hardcode v2 paths), build scripts (drop `_require_v2` guards), `scripts/generate_synthetic_cache.py` (repoint to `bloomberg_v2/`), delete `scripts/pull_drishti_data.py` (v1-only), `scripts/run_drishti_mac.sh` (drop export). Verify config resolves to v2.
- **T2 — Routes.** `src/dashboard/routes/research.py`: `/events` + `/regimes-study` read `ARTIFACTS_DIR`; strip `DRISHTI_DATA_VERSION` from error text; ADD `GET /spillover/study` serving `ARTIFACTS_DIR/spillover_study.json`.
- **T3 — Spillover-study UI.** `spillover.js` + `templates/index.html` (Spillover tab): fetch `/api/research/spillover/study`, render large/mid/combined total/net + IS/OOS. (after T2)
- **T4 — Header badge.** `src/dashboard/routes/static_data.py` + `tests/test_static_data.py`: route via `ARTIFACTS_DIR`; populate regime from `regime_study.json`, connectedness from `spillover_study.json`; drop dead reads.
- **T5 — Correctness.** `risk/stress.py` (GICS↔override-key map, exact match), `risk/returns.py` (clean gsec10y), `research/breach_classifier.py` (named-feature guard), `research/diebold_yilmaz.py` (drop deprecated `verbose`). Update tests.
- **T6 — Tests/notebooks/docs.** delete `tests/test_v2_switch.py`; reconcile `test_events_route.py`/`test_regimes_route.py`; strip env line from notebooks `08–15` (.md + .ipynb) + `notebooks/README.md`; update `CLAUDE.md`/`README.md`; add route-source test.

## Verify
`PYTHONPATH=. pytest tests/ -q` green; run notebooks headless via `run_notebook_md.py`; boot app + curl key endpoints.
