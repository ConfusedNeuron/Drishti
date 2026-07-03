# PRD — Drishti v4: Personal Portfolio Research Platform

**Date:** 2026-07-04 · **Status:** Draft for discussion · **Owner:** Pranav
**Companion doc:** `design/prd-2026-07-04-current-state.md` (what exists today)

---

## 1. Vision

Evolve Drishti from a course-demo risk dashboard into a personal, broker-connected research platform: it knows *your actual Zerodha portfolio*, tells you diagnostically where it sits relative to an efficient portfolio, what market forces are acting on it right now, and lets you run your own econometric experiments — things TradingView/Pine Script structurally cannot do (portfolio-level optimization, multivariate econometrics, ML, broker P&L integration).

**Framing rule (unchanged):** every output is educational/diagnostic. The frontier says "here is the gap between your weights and the max-Sharpe weights," never "sell X, buy Y." This matters doubly if the demo is public on a portfolio website (SEBI investment-adviser territory otherwise).

## 2. Why not TradingView

Pine Script runs per-chart on one symbol, caps cross-symbol requests at ~40, has no optimizer, no MLE, no matrix econometrics, no broker-holdings awareness, and screeners are point-in-time (survivorship-biased). Drishti's moat: your own survivorship-free 25-year dataset + portfolio-aware analytics + full Python. TradingView remains better at charting UX, realtime data, and alerts — do not rebuild those.

## 3. Features

### F1 — Zerodha portfolio sync (foundation)
Kite Connect **Personal API is free** (holdings/positions/funds; no market data — fine, prices come from our cache). Add a dashboard login flow (API key + daily access-token exchange), refresh button, and a P&L view: per holding — qty, average price, last cached price, unrealized P&L, weight, sector.
*Already exists:* `importer.load_zerodha()`. *New:* auth flow UI, token persistence, P&L panel.

### F2 — Efficient Frontier Studio (the centerpiece)
Interactive MPT on the actual portfolio.

- **Inputs:** current holdings (default) ± user-added candidates from the 433-equity universe; horizon preset (6m / 1y / 5y / 10y / 20y); long-only toggle.
- **Estimation policy (the horizon question, resolved):** frequency follows horizon —
  - 6m–1y: daily returns, EWMA-weighted covariance (recent regime matters most);
  - 3–5y: weekly returns (kills microstructure noise, still ~250 obs);
  - 10–20y: monthly returns (structural relationships; √-scaling daily vol to 20y is indefensible — vol clusters and correlations drift, the same reason we rejected √t for historical VaR).
  - Always: Ledoit-Wolf shrinkage on the covariance (N assets vs T obs), and a resampled-frontier band to show estimation uncertainty instead of a false-precision single curve.
- **Risk-free rate:** 10y G-sec yield from cache (currently ~6.9%) for long horizons; add 91-day T-bill to the next FRTL pull for short horizons.
- **Outputs:** frontier curve + uncertainty band; your portfolio plotted on it; min-variance point; **tangency portfolio + Capital Market Line** (the tangent from r_f — tangency = max-Sharpe; two-fund separation means CML points dominate the frontier); three risk presets (conservative / balanced / aggressive = target-vol points); **weight-gap table**: current weight vs selected-point weight per holding, colored by delta — diagnostic language only.
- *Already exists:* all the math (`frontier.py: efficient_frontier, min_variance, tangency`, notebook 11). *New:* shrinkage + resampling, horizon/frequency policy, route, UI.

### F3 — "What's acting on my portfolio" watchlist
Reuse the IC/Granger/spillover machinery, but conditioned on the *live portfolio's* sector mix: rank commodities/macro factors by BH-significant lagged IC and Granger causality against the portfolio's sector composites; show each factor's recent move and which holdings sit in the affected sectors. This converts the existing generic research tab into "commodities and sectors to watch, based on past behaviour, for *this* portfolio."
*Already exists:* IC, Granger, BH, sector composites. *New:* portfolio-conditioned aggregation + panel.

### F4 — Spillover Lab (previously designed, folded in)
User-driven Diebold-Yilmaz: pick any 3–12 cached series (equities/indices/commodities/macro/sector composites) via a catalog endpoint, set dates/window/horizon, compute live with caps + in-memory cache; same-shape payloads as existing spillover charts. Extends naturally into the pattern for future "labs" (DCC lab, VaR lab).

### F5 — Multi-horizon risk report
One view answering "what is my risk at each horizon": 6m/1y VaR-ES (daily, GARCH-FHS), 5y drawdown/regime exposure (weekly), 10–20y frontier position (monthly) — each labeled with its estimation frequency and window so the methodology is honest.

## 4. Deployment reality

Two modes, one codebase: **local** (full Bloomberg cache, Zerodha sync, heavy compute) and **portfolio-website demo** (Render free tier, synthetic/public data, sample portfolio, compute caps, data-source badge). Bloomberg data never leaves the machine; the demo must degrade gracefully to whatever cache it has.

## 5. Out of scope (v4)

Order placement / trade execution; alerts & notifications; CSV series upload; intraday anything; US S&P dataset integration (separate project per 2026-07-02 decision); Black-Litterman and HRP (candidate v5 items).

## 6. Sequencing

1. F1 Zerodha sync + P&L (foundation; small)
2. F2 Frontier Studio (centerpiece; medium)
3. F4 Spillover Lab (design already done; medium)
4. F3 Portfolio watchlist (builds on F1; medium)
5. F5 Multi-horizon report (assembles F2 pieces; small)
Dashboard audit (already planned) should run before or alongside F1.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Advice-like outputs on a public site (SEBI) | Diagnostic language, no ticker-level "recommendations," disclaimer banner, safety filter already in place |
| Bloomberg licensing on public demo | Synthetic/public data only on Render; badge states the source |
| Estimation garbage-in (young IPOs, short overlaps) | `filter_min_history()` already exists; shrinkage; minimum-observation guards per horizon |
| Free Kite Personal API lacks prices | By design — prices come from our own cache; document the ≤1-day staleness |
| Token handling for Zerodha | Access token stored locally only, never committed/deployed |
