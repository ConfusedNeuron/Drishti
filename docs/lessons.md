# Lessons Learned — Drishti Build (May–June 2026)

Practical knowledge from building a Bloomberg-powered quant risk platform at FRTL, IIM Calcutta.
Organized so the next project doesn't repeat the same discoveries.

---

## Bloomberg FRTL Terminal — Field & Ticker Knowledge

### Fields that are broken on FRTL (return 100% null silently)
- `PX_ADJ_CLOSE` — adjusted close field requires a terminal entitlement not available at FRTL. **Use `PX_LAST` with `adjustmentSplit=True` + `adjustmentNormal=True` in the BDH request instead** — gives the same split-and-dividend-adjusted price.
- `IS_*` fields — all income statement service fields (`IS_NET_INC`, `IS_EPS_BASIC`, `IS_EPS_DILUTED`) return null. Use `NET_INCOME`, `CF_NET_INC` instead.
- `RETURN_ON_EQY` — broken. Use `RETURN_COM_EQY`.
- `TRAIL_12M_*` fields — null in `HistoricalDataRequest`. Only work for current/reference data.
- `INDX_MEMBERS`, `INDX_MWEIGHT_HIST` — return 0 rows (entitlement). Maintain ticker lists manually.

### Bloomberg ticker codes ≠ NSE trading symbols
Many Indian equities have Bloomberg codes that differ from the NSE symbol. Bloomberg truncates long NSE symbols to a shorter internal code. Always verify on terminal before a large pull:

| NSE Symbol | Bloomberg Ticker | NSE Symbol | Bloomberg Ticker |
|---|---|---|---|
| HDFCBANK | `HDFCB IN Equity` | INFY | `INFO IN Equity` |
| ICICIBANK | `ICICIBC IN Equity` | KOTAKBANK | `KMB IN Equity` |
| BAJFINANCE | `BAF IN Equity` | HINDUNILVR | `HUVR IN Equity` |
| HCLTECH | `HCLT IN Equity` | WIPRO | `WPRO IN Equity` |
| NESTLEIND | `NEST IN Equity` | ASIANPAINT | `APNT IN Equity` |
| TATAMOTORS | `TTMT IN Equity` | HINDALCO | `HNDL IN Equity` |
| POWERGRID | `PWGR IN Equity` | TATASTEEL | `TATA IN Equity` |
| TITAN | `TTAN IN Equity` | MARUTI | `MSIL IN Equity` |

Short NSE symbols generally match directly (RELIANCE, TCS, SBIN, ONGC, ITC, LT, NTPC).

### NSE sector index tickers (Bloomberg)
Never guess these — look them up in `data/csv/all nse index.csv` or Bloomberg's index search:
- `NSENRG Index` = NSE Nifty Energy (not NSEOILGS — that doesn't exist)
- `NSEMET Index` = NSE Nifty Metal (not NSEMETAL)
- `NSEPSBK Index` = NSE Nifty PSU Bank (not NSEPBKIDX)
- `NSEREAL Index` = NSE Nifty Realty (Bloomberg also accepts NSEREALTY as alias)

### BDP validation is unreliable for large batches on FRTL
`BDP(SECURITY_NAME)` for 50 tickers at once returns partial responses — valid tickers time out and get treated as invalid. **Do not use BDP as a pre-validation gate for large pulls.** Let BDH handle errors directly via `securityError` in the response.

### Chunk size and sleep
100 tickers per `HistoricalDataRequest`, 0.25s sleep between chunks. Stable at FRTL. Larger chunks occasionally time out.

### The `WARN blpapi_subscriptionmanager.cpp` message
Harmless. Bloomberg's internal streaming subscription service. Does not affect `//blp/refdata` historical pulls. Ignore it.

---

## Data Pipeline Design

### Cache-first with per-ticker parquet files
One file per ticker (`{ticker_safe}.parquet`) in a category subdirectory (`equities/`, `indices/`, `commodities/`, `macro/`). On rerun, check file existence before pulling. This gives free resumability — interrupted pulls continue exactly where they left off.

### Category routing bug to avoid
When routing tickers to subdirectories, check specific patterns before generic ones. `GIND10YR Index` and `INVIXN Index` both contain "Index" but are macro factors, not equity indices. Check for `GIND10YR` and `INVIXN` explicitly **before** the generic `INDEX` check, or they'll land in `indices/` instead of `macro/`.

### `file_suffix` for multiple datasets per ticker
When pulling daily prices AND annual fundamentals for the same ticker set, use a filename suffix (e.g. `_annual`) to avoid overwriting. `HDFCB_IN_Equity.parquet` = daily, `HDFCB_IN_Equity_annual.parquet` = fundamentals.

### Always run `--validate` before a full pull
A field that Bloomberg accepts without error can still return 100% null. Test all candidate fields on 5 tickers before committing to a 60-minute pull.

### Keep the reference CSV
Ask Bloomberg to export the index security list (`MEMB <GO> → Export`). The CSV becomes the ground truth for ticker codes and saves debugging time. Store it in `data/csv/`.

---

## Methodology

### IC mis-specification (common mistake)
A commodity return at time t is a single scalar — identical for all stocks. Computing cross-sectional IC (rank-correlating it with a cross-section of stock returns) gives either undefined or trivially zero results. The correct approach is **time-series IC**: rolling Pearson correlation between `factor_{t-lag}` and `target_t` over a rolling window (63 days ≈ 1 quarter).

### Three VaR methods must be genuinely different
Gaussian Monte Carlo (Cholesky decompose covariance, simulate paths) ≈ parametric VaR — both assume multivariate-normal returns using the same covariance matrix. They'll be ~98% correlated. The third method must use a different distributional assumption. **GARCH-FHS** (fit GARCH to standardize residuals, bootstrap from them) is fat-tailed and genuinely different.

### Multi-day VaR scaling
`√t` scaling assumes i.i.d. returns. This contradicts the whole motivation for GARCH/regime models (volatility clustering). For historical VaR at a multi-day horizon, use **non-overlapping return windows** (sum returns over non-overlapping 10-day blocks, then take the empirical quantile). Use √t only for parametric VaR and document it as an explicit assumption.

### HMM label switching
When HMM is refit monthly in walk-forward mode, state 0 can flip between low-vol and high-vol between refits. Always **sort states by emission mean on the volatility feature** after every fit and assign canonical labels (0 = low-vol, 1 = high-vol). Without this, the regime history is discontinuous.

### Multiple testing correction
Running 280 factor × sector × lag combinations without correction will yield ~14 false positives at α=5% by chance alone. Apply **Benjamini-Hochberg FDR correction** across all p-values. Report both raw significance and BH significance. Only claim findings that survive BH.

### Diebold-Yilmaz: use Pesaran-Shin FEVD, not Cholesky
Cholesky-based FEVD is order-dependent — change the variable order and you get different results. Pesaran-Shin generalized FEVD is order-invariant. Always use generalized IRF for connectedness research.

---

## Software Engineering

### Validate before you build
Running `--validate` on 5 tickers before a full pull took 30 seconds and saved 60 minutes of a broken full pull. Build a validation mode into any large data pull script.

### Resumable by design
Any script that takes >10 minutes should be resumable. Write results incrementally (one file per item), check existence before pulling. The next run skips completed work automatically.

### Python virtual environments on Windows
Always use `python -m pip`, never bare `pip`. Bare `pip` installs to system Python (Microsoft Store default) instead of the venv. If venv activation is blocked by PowerShell execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`. Fallback: use `cmd` and `.venv\Scripts\activate.bat`.

### `__future__ annotations` at top of every file
Enables postponed evaluation of type hints — avoids `NameError` for forward references in type hints, especially important for dataclasses that reference their own type.

### tqdm for long-running loops
Always wrap long loops with `tqdm`. Use `tqdm.write()` instead of `print()` inside a tqdm loop to avoid broken progress bar output.

---

## Project Management with Claude Code

### CLAUDE.md is the memory
Every project should have a `CLAUDE.md` at the root with: what it is, current status, what's built, what's left, key design decisions, known issues, run commands. Update it at every session end. This is the context handoff between sessions.

### Commit frequently with descriptive messages
Small, focused commits with clear messages make it easy to bisect bugs and understand the evolution of the code. Each logical change (fix ticker codes, add field, fix cache bug) should be its own commit.

### Save reference data in the repo
The Bloomberg CSV (`data/csv/all nse index.csv`) was the answer to "what is the correct ticker for NSE Metal Index?" Having it committed means the answer is always available without needing the terminal. Any reference data that solves a hard lookup problem — commit it.

### Synthetic fallback is non-negotiable for demos
A demo that requires live Bloomberg access will fail at the worst moment. The synthetic data generator (`scripts/generate_synthetic_cache.py`) ensures the demo always works regardless of network or terminal availability.

### Document broken things explicitly
The Bloomberg guide (`BLOOMBERG_TERMINAL_GUIDE.md`) documents what doesn't work and why. This is as valuable as documenting what does work — it saves the next person from spending hours debugging a field that's broken by design.
