# Drishti — Status & Handoff (2026-07-07)

Everything you need to know as of the end of v4 wave 1. Written for future-you (or a fresh Claude session) picking this up cold.

---

## 1. Where things stand

**Four stacked PRs are open, awaiting YOUR merges — in this order:**

| # | PR | Branch | Contents | Tests at head |
|---|----|--------|----------|---------------|
| 1 | [#12](https://github.com/ConfusedNeuron/Drishti/pull/12) | `fix/audit-2026-07-04-sprint` | 7-task audit fix sprint (copilot honesty, badge fixes, diagnostics panel, TTL cache, MCP holdings param, Yahoo map 48→433, docs) | 193 |
| 2 | [#13](https://github.com/ConfusedNeuron/Drishti/pull/13) | `feature/v4-f1-zerodha` | F1: Kite login flow (callback + manual paste), day-scoped token cache, Holdings P&L panel | 214 |
| 3 | [#14](https://github.com/ConfusedNeuron/Drishti/pull/14) | `feature/v4-f2-frontier` | F2: Efficient Frontier Studio (5 horizons, LW shrinkage, band, CML/tangency, presets, weight-gap, new Frontier tab) | 258 |
| 4 | [#15](https://github.com/ConfusedNeuron/Drishti/pull/15) | `feature/v4-f4-spillover-lab` | F4: Spillover Lab (catalog of 502 series, capped live Diebold-Yilmaz, lab UI) | 298 |

Merge #12 first; GitHub retargets each next PR automatically. After all four: delete the branches, `git checkout main && git pull`.

**`main` is still pre-fix-sprint** (175 tests) until these merge. Current local checkout: `feature/v4-f4-spillover-lab` (top of stack).

## 2. Before merging — 5 minutes of your eyes

Nobody in the build chain had a real browser (everything was verified via API probes, contract tests, and `node --check`). Boot `uvicorn src.dashboard.app:app` and:
1. **Frontier tab** — load sample portfolio, run 1y and 20y; expect a frontier + band + CML + markers, and different numbers per horizon.
2. **Spillover tab → Spillover Lab section** — pick ~5 indices + 2 commodities, Run; expect KPI + net bars + heatmap (axes: "Shock source" / "Receiver").
3. Overview — sample import should populate the new **Holdings P&L** panel.

## 3. To actually use the Zerodha login (F1)

One-time setup (not needed for sample/CSV):
1. Create a **Kite Connect Personal app** (free) at developers.kite.trade.
2. Set its **Redirect URL** to `http://localhost:8000/api/portfolio/zerodha/callback`.
3. Put `ZERODHA_API_KEY=` and `ZERODHA_API_SECRET=` in `.env` (fields already exist in `.env.example`; `.env` is gitignored).
4. Dashboard → "⚡ Connect Zerodha" → Kite login → auto-redirect back with holdings loaded. Token is cached for the day at `data/cache/zerodha/access_token.json` (gitignored, never logged). Without the redirect URL registered, use the manual request-token paste field.

## 4. Other runtime to-dos (all optional, all deferred deliberately)

- **News/FinBERT**: one-time `curl -X POST localhost:8000/api/research/news/refresh` (downloads ~440 MB; transformers/torch already installed).
- **Yahoo map validation**: `PYTHONPATH=. python scripts/build_yahoo_map_v2.py --validate` when Yahoo stops rate-limiting; triage failures into `OVERRIDES`; prune the dead plain-`TTMT` entry.
- **91-day T-bill**: add to the next FRTL pull — the Frontier Studio currently uses the 10y G-sec yield (6.89%) as rf at all horizons (flagged in its meta).
- **Data refresh runbook**: `docs/audit-2026-07-04-dashboard.md` §5 (FRTL visit → v2 pull scripts → verify → rebuild study artifacts; weekly yfinance gap-fill now covers all 433 equities).

## 5. Deferred minors (all triaged OK-to-defer by reviewers; full lists in `.superpowers/sdd/*-lead-report.md`)

Highlights: no single-flight guard in route_cache (concurrent duplicate compute, harmless single-user); `last_price: 0` falsy-coercion inherited across importer call sites; `pct_change()` FutureWarnings in the spillover-lab resolve path; hardcoded rgba inside `badge-low_vol/high_vol` CSS (won't re-tint on non-gold themes); numeric-string `"0.25"` for frontier `point` silently falls back to tangency.

## 6. What to build next (v5 candidates, no commitments)

From `design/discussion-2026-07-04-vision-notes.md` §5 and the PRD's out-of-scope list:
- **F3 portfolio-impact watchlist** (the remaining PRD feature): IC/Granger/spillover conditioned on the live portfolio's sector mix — "what's acting on MY portfolio now".
- **F5 multi-horizon risk report** (assembles F2 pieces + VaR/ES per horizon).
- Regime-conditioned frontier (HMM × F2 — the honest answer to "markets are dynamic"); Black-Litterman; HRP; walk-forward frontier backtest (does tangency rebalancing beat buy-and-hold?); Monte Carlo goal simulator; surface remaining notebook-only analytics (EVT, performance ratios, Amihud, Altman).
- **Hosting**: personal = local + Tailscale; public demo = existing Render deploy (synthetic data). **Kite-MCP interop demo**: any Claude client with both Zerodha's Kite MCP and `risk_mcp/server.py` can pipe real holdings into the risk tools (unblocked by fix-sprint T5) — a genuinely distinctive portfolio-website demo.
- US S&P 500 sibling project (`../sp500_data/` + `pip install -e` this repo) — separate repo per the 2026-07-02 decision.

## 7. Process notes (what worked, what to keep)

The wave-1 protocol — **Fable designs → Opus Lead decomposes & drives → Sonnet implements → fresh Opus reviews per task → Fable adjudicates independently** — caught real defects at every layer: pydantic bool-coercion turning `{"point": true}` into a max-risk target (Opus review), a transposed DY heatmap whose root cause was an error in the *design doc* about pandas `to_dict()` orientation (Opus review), and 10y/20y frontiers silently estimating from 5y of data (Fable's gate). Operational lessons: sibling agents can't SendMessage each other (relay through the main session); a Lead that ends its turn "waiting" with no live children is deadlocked — prefer synchronous child dispatches; 529s/session limits kill agents mid-task — the `.superpowers/sdd/progress.md` ledger is the recovery map.

Design docs for all three features: `docs/superpowers/specs/2026-07-06-f{1,2,4}-*-design.md` (committed). Lead reports + task briefs: `.superpowers/sdd/` (gitignored, local only).

## 8. Key reference docs

- `design/prd-2026-07-04-personal-research-platform.md` — the v4 vision (F1–F5)
- `design/discussion-2026-07-04-vision-notes.md` — TradingView gap analysis, Kite MCP facts, MPT/horizon reasoning, idea backlog, decisions log
- `docs/audit-2026-07-04-dashboard.md` — audit findings + hosting + data runbook
- `presentation/resume-pointers.md` (local, gitignored) — resume bullets; updated with wave-1 additions
- `CLAUDE.md` — session-by-session history (Sessions 1–13)
