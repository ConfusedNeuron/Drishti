# Drishti — Portfolio Risk Analytics

Local-first quant risk platform for Indian equity portfolios.
IIM Calcutta PGDBA, Financial Risk Management course project.

---

## Quick Start (Offline / Synthetic Data)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Generate synthetic Bloomberg cache (works without a Bloomberg terminal)
python scripts/generate_synthetic_cache.py

# Start the dashboard
uvicorn src.dashboard.app:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 → Load Sample Portfolio → Run Risk Analysis.

---

## Data Pull at FRTL (Bloomberg Terminal)

Run these on the Bloomberg terminal machine:

```bat
cd C:\Users\User\Pranav\drishti
.venv\Scripts\activate
python scripts\pull_drishti_data.py --validate          # test fields on 5 tickers first
python scripts\pull_drishti_data.py --skip-equities     # fast first pass (~5 min)
python scripts\pull_drishti_data.py                     # full pull (~60 min)
```

Copy `data\cache\bloomberg\` to your laptop before the demo.

Optional public-data gap-fill (yfinance + FRED) from the last Bloomberg date onward —
`read_merged()` blends them with Bloomberg rows winning on overlap:

```bash
python scripts/pull_public_data.py
```

---

## What's built

| Module | What it does |
|--------|-------------|
| `src/bloomberg/cache.py` | Per-ticker parquet cache; `read_merged()` blends Bloomberg + public data |
| `src/bloomberg/client.py` | BLPAPI session + BDH/BDP; graceful cache fallback |
| `src/bloomberg/tickers.py` | Zerodha symbol → Bloomberg ticker mapping |
| `src/portfolio/importer.py` | Load from sample JSON / CSV / Zerodha Kite API |
| `src/risk/var.py` | Historical VaR (non-overlapping windows), Parametric, **GARCH-FHS** |
| `src/risk/backtest.py` | Kupiec LR test + Christoffersen independence test |
| `src/risk/es.py` | Expected Shortfall |
| `src/risk/contribution.py` | Component VaR (marginal contribution) |
| `src/risk/drawdown.py` | Max drawdown, current drawdown, recovery |
| `src/risk/stress.py` | COVID / rate-hike / crude / INR / election scenarios |
| `src/research/hmm.py` | 2-state Gaussian HMM; walk-forward; canonical label sorting |
| `src/research/ic.py` | Time-series IC + Granger causality + Benjamini-Hochberg FDR |
| `src/research/dcc_garch.py` | DCC-GARCH dynamic correlations (2-step Engle estimator) |
| `src/research/diebold_yilmaz.py` | Diebold-Yilmaz connectedness (VAR + generalized FEVD) |
| `src/research/walk_forward.py` | Walk-forward OOS Sharpe per (factor × sector) pair |
| `src/research/news.py` | RSS headlines + FinBERT sentiment, file-cached |
| `src/research/breach_classifier.py` | XGBoost next-day VaR-breach probability |
| `src/risk/performance.py` | Sharpe / Treynor / Jensen-α / beta (FRM Wk3) |
| `src/risk/ewma.py` | EWMA / RiskMetrics volatility & covariance (λ=0.94) |
| `src/risk/evt.py` | EVT-VaR / ES via Peaks-Over-Threshold + GPD (McNeil-Frey) |
| `src/risk/extreme_value_vol.py` | Parkinson / Garman-Klass / Rogers-Satchell range volatility |
| `src/portfolio/frontier.py` | Markowitz efficient frontier / min-variance / tangency |
| `src/research/tar.py` | Two-regime Threshold Autoregression + bootstrap threshold test |
| `src/research/cointegration.py` | Johansen cointegration + VECM (statsmodels) |
| `src/research/credit.py` | Altman Z-score credit screen |
| `src/research/liquidity.py` | Amihud illiquidity ratio |
| `src/copilot/memo.py` | Deterministic risk memo (no LLM required) |
| `src/dashboard/app.py` | FastAPI backend (StaticFiles + Jinja2 + `/learn`) |
| `src/dashboard/templates/` + `static/` | Jinja2 templates, split CSS/JS, multi-theme picker |
| `risk_mcp/` | MCP server exposing 6 risk tools |

## Dashboard

5-tab Plotly.js single-page app rendered from Jinja2 templates
(`src/dashboard/templates/base.html` + `index.html` + `learn.html`), with CSS/JS
split under `static/css/` and `static/js/`, a `/learn` methodology page (KaTeX +
glossary), and a CSS-variable multi-theme picker.

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/portfolio/import/sample` | Load sample portfolio |
| `POST /api/portfolio/import/csv` | Upload CSV |
| `POST /api/portfolio/import/zerodha` | Import via Zerodha Kite |
| `GET  /api/portfolio/current` | Current loaded snapshot |
| `POST /api/risk/summary` | Full risk: VaR×3, ES, backtest, contribution, stress |
| `GET  /api/risk/drawdown-series` | Drawdown time series |
| `GET  /api/research/regime` | HMM regime + regime-conditioned VaR |
| `GET  /api/research/ic` | IC / Granger across factors × sectors |
| `GET  /api/research/spillover` | Diebold-Yilmaz connectedness table |
| `GET  /api/research/spillover/rolling` | Rolling total connectedness |
| `GET  /api/research/dcc` | DCC-GARCH time-varying correlations |
| `GET  /api/research/walkforward` | Walk-forward OOS Sharpe matrix |
| `GET  /api/research/news` | Cached news sentiment |
| `POST /api/research/news/refresh` | Re-fetch RSS + re-score with FinBERT |
| `GET  /api/research/breach` | XGBoost next-day breach probability |
| `POST /api/copilot/memo` | Deterministic risk memo |
| `POST /api/copilot/ask` | LLM copilot (requires `LLM_API_KEY` in `.env`) |
| `GET  /api/static-data` | Bloomberg coverage stats (cached) |
| `GET  /` · `GET /learn` · `GET /health` | Dashboard, methodology page, health check |

## Risk MCP server

```bash
python risk_mcp/server.py
```

Six tools wrapping the analytics for any MCP client (Claude Desktop, etc.):
`calculate_portfolio_risk`, `get_var_backtest`, `get_current_regime`,
`get_factor_signals`, `run_stress_test`, `generate_risk_memo`. A word-boundary
safety filter blocks investment-advice prompts.

## Research Notebooks (v3 — course-grounded findings)

Copy-paste Jupyter notebooks under `notebooks/08`–`15` present the analysis as a
narrated research story, grounded in the FRM (Weeks 1–10) and SAAPM time-series
courses, with **pedagogical layering** (the basic model as taught first, then
Drishti's advanced version). They run locally against `data/cache/bloomberg_v2/`
with matplotlib + seaborn and are validated headless by `scripts/run_notebook_md.py`:

| Notebook | Topic |
|----------|-------|
| `08_growth_trends` | Normalized growth + the raw→log→difference transformation ladder |
| `09_risk_tables` | Variance-based risk tables + Sharpe / Treynor / Jensen |
| `10_covariance` | Sample / EWMA / Ledoit-Wolf covariance + rolling correlation |
| `11_mpt_frontier` | Markowitz efficient frontier, min-variance & tangency, CML |
| `12_regime_scatter` | TAR phase-plot regimes, tied back to HMM + 20%-rule bull/bear |
| `13_advanced_techniques` | Full Box-Jenkins → ARIMA/SARIMA → GARCH/EGARCH/EWMA → EVT-VaR |
| `14_spillover` | VAR → Granger → IRF → FEVD → Diebold-Yilmaz; Johansen → VECM |
| `15_credit_liquidity` | Altman Z-score + Amihud illiquidity screens |

`scripts/pull_ohlc_frtl.py` pulls OHLC for the full v2 universe to feed the
range-based volatility estimators (notebook 13). See `notebooks/README.md` for the
full FRM/SAAPM syllabus-coverage matrix. Full method derivations are in
`docs/methodology.html`.

## Key Methodological Choices (vs. docs)

- **GARCH-FHS** as the 3rd VaR method (not Gaussian MC, which ≈ parametric)
- **Non-overlapping 10-day windows** for multi-day historical VaR (not √t)
- **Canonical HMM label sorting** by emission mean of the rolling-volatility feature, to prevent state flip across walk-forward refits
- **Time-series IC** (rolling correlation of lagged factor vs. target) — not cross-sectional scalar IC, which is undefined
- **Benjamini-Hochberg FDR correction** across all factor × sector × lag combinations

## Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

160+ tests covering VaR methods, Kupiec/Christoffersen, IC + BH correction,
walk-forward, cache merge, news sentiment, breach classifier, static data, and the
v3 analytics helpers (performance ratios, EWMA, EVT, range volatility, TAR,
cointegration, frontier, Altman, Amihud).

## Disclaimer

Educational risk analytics only. Not investment advice.
Bloomberg data via FRTL, IIM Calcutta — for academic use only, not for redistribution.
