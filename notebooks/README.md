# Drishti Research Notebooks

Two families of notebooks:

- **`01`–`07`** — BQuant specs that run inside Bloomberg's hosted Python at FRTL
  (data pull, factor IC, Granger, HMM, walk-forward, DCC-GARCH/spillover, VaR
  backtesting). These export JSON/Parquet artifacts.
- **`08`–`15`** — **v3 local findings notebooks**: copy-paste Jupyter notebooks
  that run on your machine against `data/cache/bloomberg_v2/`, presenting the
  analysis as a narrated research story grounded in the FRM (Weeks 1–10) and
  SAAPM time-series courses, with **pedagogical layering** (the basic model as
  taught first, then Drishti's advanced version). Charts use matplotlib + seaborn
  and save to `notebooks/figures/<nb>/` (gitignored).

## Running the v3 notebooks

Paste the `## Cell N [CODE]` blocks into a Jupyter notebook in order, **or**
validate one end-to-end headless with the harness:

```bash
source .venv/bin/activate
MPLBACKEND=Agg PYTHONPATH=. python scripts/run_notebook_md.py notebooks/08_growth_trends.md
```

Each notebook's Cell 2 sets `DRISHTI_DATA_VERSION=v2` and a headless matplotlib
backend, so they run without a display.

| Notebook | Topic | Course |
|----------|-------|--------|
| `08_growth_trends` | Normalized growth + raw→return→log→difference transformation ladder + drawdown | SAAPM Wk1 |
| `09_risk_tables` | Variance-based risk tables + Sharpe / Treynor / Jensen-α + risk-return scatter | FRM Wk1, Wk3 |
| `10_covariance` | Sample / EWMA / Ledoit-Wolf covariance, correlation heatmaps, rolling correlation | FRM Wk1 |
| `11_mpt_frontier` | Markowitz efficient frontier, min-variance & tangency, capital market line | FRM Wk1 |
| `12_regime_scatter` | TAR phase-plot regimes (LOESS + threshold + bootstrap test), tied to HMM + 20%-rule | SAAPM Wk4 |
| `13_advanced_techniques` | Full Box-Jenkins → ARIMA/SARIMA → GARCH/EGARCH/GJR → EWMA → EVT-VaR → range vol, on all 17 index+sector series | SAAPM Wk1–4, FRM Wk7/8 |
| `14_spillover` | VAR → Granger → IRF → Cholesky FEVD → generalized FEVD/Diebold-Yilmaz → rolling connectedness → DCC → network; Johansen → VECM | SAAPM Wk3/4 |
| `15_credit_liquidity` | Altman Z-score (worked example) + reduced credit-health screen + Amihud illiquidity | FRM Wk9 |

`scripts/pull_ohlc_frtl.py` pulls OHLC for the v2 universe to feed the range-based
volatility estimators in notebook 13 (that section skips gracefully until the
`ohlc/` cache exists).

## Syllabus coverage matrix

Legend: ✅ done · ⚠️ partial · ⊘ out-of-scope for a buy-side equity tool.

### FRM (Samit Paul) — Weeks 1–10
| Wk | Topic | Status | Where |
|----|-------|--------|-------|
| 1 | Log/simple returns, variance, covariance, diversification | ✅ | 08, 09, 10 |
| 1 | Mean-variance efficient frontier | ✅ | 11 |
| 1 | Market / size / value factors | ⚠️ | data present; factor portfolios later |
| 2 | VaR concept | ✅ | 13 |
| 2 | RAROC, economic capital, Basel | ⊘ | bank capital adequacy |
| 3 | Sharpe / Treynor / Jensen-α | ✅ | 09 |
| 3 | Insurance / mutual-fund agency | ⊘ | — |
| 4–5 | Duration, gap, immunization | ⊘ | bond banking-book |
| 6 | FX quotes, arbitrage, hedging | ⊘ | (USDINR factor/stress partially) |
| 7 | Stationarity, vol clustering, GARCH(1,1), AIC/BIC | ✅ | 13 |
| 7 | EWMA (RiskMetrics) | ✅ | 10, 13 |
| 7 | EGARCH / GJR-TGARCH, news-impact, leverage | ✅ | 13 |
| 7 | Extreme-value vol (Parkinson/GK/RS) | ✅ | 13 (needs OHLC pull) |
| 8 | Historical / parametric / conditional VaR, ES | ✅ | 13 + core app |
| 8 | EVT-based VaR (POT/GPD) | ✅ | 13 |
| 8 | Kupiec / Christoffersen backtest | ✅➕ | core app |
| 9 | Altman Z-score; credit scoring | ✅ | 15 |
| 9 | Liquidity: Amihud / impact cost | ✅ | 15 |
| 9 | LCR / NSFR | ⊘ | — |
| 10 | Operational risk (Basel, Poisson×lognormal) | ⊘ | — |

### SAAPM (time-series) — Weeks 1–4
| Topic | Status | Where |
|-------|--------|-------|
| ADF, Ljung-Box, ARCH-LM | ✅ | 13 |
| Full Box-Jenkins ARIMA/SARIMA | ✅ | 13 |
| GARCH-t / skew-t / EGARCH univariate | ✅ | 13 |
| TAR threshold regime | ✅ | 12 |
| VAR → Granger → IRF → FEVD | ✅ | 14 |
| Johansen cointegration → VECM | ✅ | 14 |
| DCC / ADCC-GARCH, HMM (Markov-switching) | ✅ | 12, 14 + core app |

All notebooks cite *Bloomberg Terminal, FRTL, IIM Calcutta* and use
educational/diagnostic language only — never investment advice.
