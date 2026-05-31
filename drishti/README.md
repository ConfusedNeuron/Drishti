# Drishti — Portfolio Risk Analytics

Local-first quant risk platform for Indian equity portfolios.
IIM Calcutta PGDBA, Financial Risk Management course project.

---

## Quick Start (Offline / Synthetic Data)

```bash
cd drishti
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Generate synthetic Bloomberg cache (works without Bloomberg terminal)
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
python scripts/pull_bloomberg_data.py --output-dir "C:\Users\User\Pranav\drishti\data\cache\bloomberg"
```

Copy `data/cache/bloomberg/` to your laptop before the demo.

---

## What's built

| Module | What it does |
|--------|-------------|
| `src/bloomberg/cache.py` | Parquet cache (ticker → file); cache-first reads |
| `src/bloomberg/client.py` | BLPAPI session + BDH/BDP; graceful CSV fallback |
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
| `src/copilot/memo.py` | Deterministic risk memo (no LLM required) |
| `src/dashboard/app.py` | FastAPI backend |
| `src/dashboard/static/index.html` | Single-page dashboard (Plotly.js) |

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/portfolio/import/sample` | Load sample portfolio |
| `POST /api/portfolio/import/csv` | Upload CSV |
| `POST /api/risk/summary` | Full risk: VaR×3, ES, backtest, contribution, stress |
| `GET /api/research/regime` | HMM regime + regime-conditioned VaR |
| `GET /api/research/ic` | IC/Granger across factors × sectors |
| `GET /api/research/spillover` | Diebold-Yilmaz connectedness table |
| `GET /api/research/dcc` | DCC-GARCH time-varying correlations |
| `POST /api/copilot/memo` | Deterministic risk memo |
| `POST /api/copilot/ask` | LLM copilot (requires `LLM_API_KEY` in `.env`) |

## Key Methodological Fixes (vs. docs)

- **GARCH-FHS** as the 3rd VaR method (not Gaussian MC which ≈ parametric)
- **Non-overlapping 10-day windows** for multi-day historical VaR (not √t)
- **Canonical HMM label sorting** (by emission variance) to prevent state flip across walk-forward refits
- **Time-series IC** (rolling correlation of lagged factor vs. target) — not cross-sectional scalar IC which is undefined
- **Benjamini-Hochberg FDR correction** across all factor × sector × lag combinations

## Tests

```bash
PYTHONPATH=. pytest tests/ -v
```

14 tests covering VaR methods, Kupiec, Christoffersen, IC, BH correction.

## Disclaimer

Educational risk analytics only. Not investment advice.
Bloomberg data via FRTL, IIM Calcutta — for academic use only, not for redistribution.
