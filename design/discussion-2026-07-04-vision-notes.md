# Discussion Notes — 2026-07-03/04: Drishti beyond the course

Companion to `design/prd-2026-07-04-current-state.md`, `design/prd-2026-07-04-personal-research-platform.md`, and `docs/audit-2026-07-04-dashboard.md`. This file captures the conversation content not already in those docs: the TradingView comparison, broker-data facts, the finance reasoning, and the full idea backlog.

---

## 1. Pranav's stated intent (verbatim spirit)

- The tool can be much more than a course demo — usable for research.
- Dashboard should *run code on user input* (e.g., spillover on user-chosen series), not only show precomputed artifacts.
- Broker-connected: use Zerodha holdings (avg price + current price → P&L) plus our historical data to build an MPT efficient frontier, with the risk-free tangent, offering different risk levels and diagnostic keep/trim gaps.
- Multiple horizons (6m / 1y / 5y / 10y / 20y); open question raised: how to estimate long-term risk when markets are dynamic — daily data always, or aggregate to weekly/monthly?
- Surface which commodities/sectors to watch that affect the current portfolio, based on past behaviour.
- Don't throw away the work: make it usable, host it, keep data updated, let others research via Zerodha's MCP, and improve resume pointers along the way.
- Sequencing decision: **fix what exists first**, then decide which v4 features to build.

## 2. TradingView / Pine Script comparison (research, 2026-07-04)

- Plans: Basic (free), Essential ~$14.95/mo, Plus ~$34.95, Premium ~$69.95, Ultimate ~$239.95. Paid tiers buy *quantity* (indicators per chart 2-3→25, charts per layout 1→8, alerts 1-3→400+, second-based intervals, deeper history) — not a different analytical engine.
- Pine Script structural limits: per-chart single-symbol execution; ~40 `request.security` cross-symbol calls; 127-element tuple cap; no optimizer, no MLE, no matrix econometrics; screeners are point-in-time (survivorship-biased).
- Therefore Drishti's defensible moat vs TradingView:
  1. analytics on *your actual holdings* (portfolio VaR/ES, component VaR, backtests);
  2. portfolio optimization (frontier/tangency = quadratic programming);
  3. multivariate econometrics (DCC-GARCH, Diebold-Yilmaz, HMM, Granger/IC + BH);
  4. ML/NLP (XGBoost breach, FinBERT);
  5. survivorship-free 26-year constituent history.
- Don't rebuild what TV does better: charting UX, realtime ticks, alerts, community scripts.

## 3. Zerodha data facts (verified 2026-07-04)

- Kite Connect **Personal API: free** — holdings (symbol, exchange, ISIN, qty, **average_price**, last_price, close_price, P&L), positions, orders, funds. No live quotes/historical candles on free tier — irrelevant for us, prices come from our own cache. Paid ₹500/mo adds market data.
- `importer.load_zerodha()` already consumes this; missing piece is only the UI login flow (audit A2 / PRD F1).
- **Kite MCP** (official, hosted `mcp.kite.trade`, OAuth, read-only, revocable): the interop story is a user's Claude connecting to BOTH Kite MCP and Drishti's risk MCP — Claude passes holdings from one to the other; Drishti never touches credentials. Blocked only by audit finding A1 (tools must accept holdings as arguments).

## 4. Finance reasoning settled in discussion

- **The "tangent from risk-free rate"**: Capital Market Line; tangency point = maximum-Sharpe portfolio; two-fund separation means CML mixes of (risk-free asset + tangency portfolio) dominate the frontier — risk levels (conservative/balanced/aggressive) are points along it. `src/portfolio/frontier.py:tangency()` already implements the math; 10y G-sec yield (~6.9%) is in the macro cache; add 91-day T-bill at next FRTL pull for short horizons.
- **Horizon vs data frequency** (Pranav's open question, resolved): match return frequency to decision horizon — daily + EWMA/GARCH for ≤1y (recent regime dominates); weekly for ~5y; monthly for 10-20y (structural relationships; daily microstructure noise and vol clustering make √-scaling daily risk to decades indefensible — same reason the project rejected √t in historical VaR). Frequency and window length are separate knobs. Show estimation honesty: Ledoit-Wolf shrinkage + resampled frontier band, and (uniquely, since we have HMM) a regime-conditioned frontier as the answer to "markets are dynamic."

## 5. Idea backlog beyond the v4 PRD (candidate v5+)

- Black-Litterman (blend user views with market equilibrium; fixes MPT estimation garbage-in)
- Hierarchical Risk Parity / risk parity (no expected-return estimates needed)
- Monte Carlo goal simulator ("P(portfolio ≥ ₹X in N years)")
- Benchmark attribution vs NIFTY (allocation/selection split)
- India tax-aware rebalancing diagnostics (LTCG/STCG lot ages)
- Walk-forward frontier backtest (does tangency rebalancing beat buy-and-hold? — publishable-style research question)
- Scheduled weekly PDF risk memo; alerts via cron
- Surface notebook-only analytics in dashboard: EVT tail VaR, performance ratios, range-based vol, TAR, Johansen, Altman, Amihud (audit A10)
- US S&P 500 sibling project using `../sp500_data/` via `pip install -e` of this repo (decision 2026-07-02: separate project)

## 6. Decisions log (this discussion)

| Date | Decision |
|---|---|
| 2026-07-02 | S&P 500 work = separate sibling project; `presentation/` gitignored, not committed |
| 2026-07-03 | Spillover Lab approach A (parameterized sync endpoint + catalog + caps); folded into v4 PRD as F4 |
| 2026-07-04 | v4 PRD written (F1 Zerodha UI → F2 Frontier Studio → F4 Spillover Lab → F3 watchlist → F5 horizon report) |
| 2026-07-04 | Audit before features: fix-what-exists sprint is next (audit doc §6) |
