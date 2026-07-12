# Dashboard & Platform Audit — 2026-07-04

Method: enumerated all 25 routes, probed every endpoint in-process against the real v2 cache (TestClient), cross-referenced every `/api/` path referenced in `static/js/` and templates, inspected MCP tool plumbing and optional deps. Test suite: 175 passing.

## 1. Verified working (endpoint probe, real cache)

All 19 user-facing endpoints returned **200**:

| Endpoint | Time | Notes |
|---|---|---|
| POST /api/portfolio/import/sample | 0.0s | in-memory snapshot |
| GET /api/portfolio/current | 0.0s | |
| POST /api/risk/summary | 1.0s | VaR×3, ES, backtests, component VaR, stress |
| GET /api/risk/drawdown-series | 0.0s | |
| GET /api/research/regime | **7.8s** | HMM walk-forward, recomputed every call |
| GET /api/research/ic | 1.4s | |
| GET /api/research/dcc | 1.2s | |
| GET /api/research/spillover (+/rolling, /study) | ≤0.3s | |
| GET /api/research/walkforward | 0.6s | |
| GET /api/research/diagnostics | 0.2s | works — but **no UI calls it** |
| GET /api/research/events, /regimes-study | 0.0s | artifact-backed |
| GET /api/research/breach | **6.5s** | model + features recomputed every call |
| GET /api/research/news | 0.0s | `{"status":"no_cache"}` until refreshed |
| GET /api/static-data | 0.0s | works — but **no UI calls it** |
| POST /api/copilot/memo, /ask | 0.2s | /ask falls back to memo without API key |

Solid and genuinely done: risk engine + backtests, spillover suite (static/rolling/study), events & regimes studies, IC/Granger/BH, walk-forward, themes/learn page/tooltips, 175 tests, notebooks 01–15, methodology docs.

## 2. Findings (ranked)

- **A1 — MCP server cannot see the imported portfolio.** `risk_mcp/tools.py:_load_portfolio()` reads the dashboard's in-memory `_current_snapshot`, but the MCP server runs as a **separate process** — it always analyzes the sample portfolio regardless of what the dashboard imported. Fix: give MCP tools an explicit holdings parameter and/or a shared snapshot file. (This also unblocks the Kite-MCP interop story, §4.)
- **A2 — Zerodha import has no UI.** `POST /api/portfolio/import/zerodha` works (`kiteconnect` installed) but nothing in the frontend calls it. = v4 feature F1.
- **A3 — Dead endpoint `/api/static-data`.** Built for the header badge; badge is actually fed by `/api/risk/summary` + `/api/research/regime`. Either wire it (instant badge on page load — its original intent) or delete it.
- **A4 — Diagnostics ladder orphaned.** `/api/research/diagnostics` (ADF→LB→ARCH-LM→BIC→CCC) works in 0.2s, absent from UI.
- **A5 — No caching on heavy endpoints.** regime 7.8s and breach 6.5s recompute per call. Memoize keyed on (portfolio, data version).
- **A6 — Public-data gap-fill can't cover v2.** `yahoo_tickers.json` maps 48 equities (v1 universe) vs 433 in v2; indices/commodities/macro partial. Weekly gap-fill silently misses most of the universe.
- **A7 — Portfolio state is a process-global.** Fine single-user local; resets on restart; wrong for any multi-user hosting.
- **A8 — News panel dormant until first refresh** (transformers/torch ARE installed now — CLAUDE.md checklist stale); first refresh downloads FinBERT ~440MB.
- **A9 — Copilot "AI" mode unlabeled.** Without `ANTHROPIC_API_KEY`, /ask silently degrades to the deterministic memo. Honest, but the UI should say which mode answered.
- **A10 — Notebook-only analytics invisible to the dashboard:** efficient frontier + tangency, EVT tail VaR, Sharpe/Treynor/Jensen, EWMA, range-based vol, TAR, Johansen/VECM, Altman, Amihud. The frontier gap = v4 F2.
- **A11 — Data ends 2026-06-12** and freshness depends on FRTL visits (see §5).

## 3. Hosting

Two modes, matching the licensing constraint (Bloomberg-derived data must not be publicly served):

1. **Personal (real data, real portfolio):** run locally; for access from anywhere, **Tailscale** (free mesh VPN — dashboard on your phone, zero exposure) or Cloudflare Tunnel with access policy. This is the primary mode.
2. **Public demo (portfolio website):** the existing **Render free-tier deploy** (render.yaml + weekly.yml already in repo) on synthetic/public data — cold-starts after 15 min idle; fine for a demo link. If cold starts annoy, a small VPS (Hetzner/DigitalOcean ~₹400–500/mo) or Fly.io. Add a data-source badge so demo ≠ Bloomberg.

## 4. Letting others research via Zerodha's Kite MCP

Zerodha hosts an official **Kite MCP** (`mcp.kite.trade`, OAuth login, read-only, revocable). The clean interop: a user's Claude Desktop/claude.ai config includes **both** Kite MCP and Drishti's risk MCP. Claude fetches their holdings from Kite MCP, then passes them into Drishti tools, which run VaR/regime/stress/factor analytics on Drishti's historical cache. Drishti never touches their credentials — Zerodha handles identity.

Prerequisites (small): fix A1 — tools must accept holdings as arguments (e.g. every tool takes optional `holdings` JSON, or a `set_portfolio` tool); expose the FastMCP server over SSE/HTTP if remote users should connect to a hosted instance (public instance = synthetic/public data only), or they run it locally via git clone.

## 5. Keeping data updated (runbook)

| Layer | How | Cadence |
|---|---|---|
| Bloomberg v2 parquets | FRTL visit: `pull_drishti_v2.py` (resumable) + `pull_ohlc_frtl.py`, copy `bloomberg_v2/` home, run `verify_v2_cache.py` | Each campus FRTL visit (monthly-ish) |
| Between visits | `pull_public_data.py` (yfinance+FRED merge, Bloomberg wins) — **extend `yahoo_tickers.json` to v2 universe first (A6)**; NSE symbols map mechanically (`RELIANCE.NS`) | Weekly (CI already scheduled) |
| Research artifacts | `build_spillover_study.py` / `build_events_study.py` / `build_regime_study.py` after any data refresh | After each refresh |
| Breach model | `train_breach_classifier.py` | Quarterly / after big refresh |
| News sentiment | POST /api/research/news/refresh | On demand |

## 6. Recommended order of work

1. **Quick wins sprint (this audit's fixes):** A3 wire-or-delete static-data, A4 diagnostics panel, A5 caching, A9 mode label, A8 news refresh once, CLAUDE.md corrections.
2. **A1 MCP holdings param** — small, unblocks the Kite-MCP interop demo (resume-worthy on its own).
3. **A6 v2 yahoo map** — makes the weekly gap-fill real.
4. Then v4 PRD sequencing: F1 Zerodha UI → F2 Frontier Studio → F4 Spillover Lab → F3 watchlist → F5 horizon report.

## 7. Resume pointers (delta)

Existing `presentation/resume-pointers.md` bullets remain valid. New bullets unlocked as the above lands:
- *Interoperable MCP design:* "Designed MCP interop letting any Claude user pipe live Zerodha holdings (via Kite MCP OAuth) into a custom risk-analytics MCP — zero credential handling."
- *Deployment:* "Shipped dual-mode deployment: full-data personal instance behind Tailscale + license-safe synthetic public demo with weekly CI refresh."
- *Frontier Studio (after F2):* "Built an interactive Markowitz studio (Ledoit-Wolf shrinkage, resampled frontier, CML/tangency) over live broker holdings with horizon-matched return frequencies."
Keep the "175 vs 163 tests" caveat discipline: update counts as they change.
