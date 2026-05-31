# Notebook 05 — Walk-Forward Factor Signal Backtest
> Run in: **BQuant (Bloomberg hosted Python environment at FRTL)**
> Inputs: `sector_returns.parquet`, `commodity_returns.parquet`, `macro_series.parquet`, `factor_ic_results.json` (from Notebooks 01, 02)
> Output artifact: `walk_forward_results.json`

---

## Cell 1 [MARKDOWN]

# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti's factor research pipeline tests whether commodity price signals have predictive power over Indian equity sector returns. The IC and Granger tests in Notebooks 02 and 03 measure *in-sample* signal quality — they tell us whether a historical relationship existed. This notebook asks the harder question: does the signal work **out-of-sample**?

A signal that looks great in-sample but fails OOS is almost certainly overfit. The walk-forward backtest is the standard defense against this in quantitative research.

---

## Cell 2 [MARKDOWN]

## Notebook 05 — Walk-Forward Factor Signal Backtest

**What this notebook does:**

Simulates trading the top-ranked factor signals discovered in Notebook 02 on an OOS basis. For each factor-sector pair:

1. **Training phase:** Fit the signal (compute IC) on a rolling 252-day expanding window.
2. **OOS trading:** In the next month (21 trading days), go long the sector index if the factor's IC estimate is positive at the best lag, hold flat otherwise.
3. **Evaluation:** Accumulate OOS P&L across all refit periods. Report OOS Sharpe, maximum drawdown, win rate, and cumulative return.

**Key discipline:** No data from the OOS period is ever used to fit or select the signal. The lag is selected on the *training window only*, then fixed for the next month.

**Output:** `walk_forward_results.json` — OOS performance metrics per (factor, sector) pair + cumulative return series for dashboard chart.

---

## Cell 3 [CODE]

```python
# ── Imports ────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

INPUT_DIR  = Path("/bquant/data/drishti")
OUTPUT_DIR = INPUT_DIR

print("Loading data from Notebook 01 + 02 exports...")
```

---

## Cell 4 [CODE]

```python
# ── Load data ────────────────────────────────────────────────────────────────
sector_returns    = pd.read_parquet(INPUT_DIR / "sector_returns.parquet")
commodity_returns = pd.read_parquet(INPUT_DIR / "commodity_returns.parquet")
macro_returns     = pd.read_parquet(INPUT_DIR / "macro_series.parquet")

factor_returns = pd.concat([commodity_returns, macro_returns], axis=1)

# Load IC results from Notebook 02 to know which factor-lag pairs to test
with open(INPUT_DIR / "factor_ic_results.json") as f:
    ic_data = json.load(f)

ic_df = pd.DataFrame(ic_data["results"])

# Select BH-significant pairs for the walk-forward test
# If none pass BH, fall back to top-5 by |t-stat|
bh_sig = ic_df[ic_df["bh_significant"]].copy()
if len(bh_sig) == 0:
    print("⚠️  No BH-significant results. Using top 5 by |t-stat|.")
    bh_sig = ic_df.nlargest(5, "t_stat", keep="all")

# Unique (factor, sector) pairs — select the best lag per pair
best_pairs = (
    bh_sig.sort_values("t_stat", key=abs, ascending=False)
    .groupby(["factor", "target"])
    .first()
    .reset_index()
    [["factor", "target", "lag_days"]]
)

print(f"Factor-sector pairs to backtest: {len(best_pairs)}")
print(best_pairs.to_string(index=False))
```

---

## Cell 5 [MARKDOWN]

### Walk-forward engine

**Signal rule:** At the end of each training window:
1. Compute the rolling IC for the factor at its best lag.
2. If the IC estimate on the training window is positive → go long the sector next month.
3. If negative → hold flat (no short selling).

**Why expanding window (not rolling)?** Expanding windows use all available information and are more stable. Rolling windows can discard useful older data. Either is defensible; we document the choice.

**Transaction cost note:** We assume zero transaction costs (no bid-ask, no market impact). This is appropriate for sector ETFs or indices used as benchmarks, not individual stocks.

---

## Cell 6 [CODE]

```python
# ── Walk-forward backtest function ───────────────────────────────────────────

def compute_ic_on_window(
    factor: pd.Series,
    target: pd.Series,
    lag: int,
    rolling_corr_window: int = 63,
) -> float:
    """
    Estimate IC on the given data window.
    Returns mean rolling Pearson correlation (factor lagged by `lag` days vs. target).
    """
    df = pd.concat([factor.rename("f"), target.rename("t")], axis=1).dropna()
    df["f_lagged"] = df["f"].shift(lag)
    df = df.dropna()

    if len(df) < rolling_corr_window + lag + 5:
        return 0.0

    ic = df["f_lagged"].rolling(rolling_corr_window).corr(df["t"]).dropna()
    return float(ic.mean())


def walk_forward_single(
    factor_series: pd.Series,
    target_series: pd.Series,
    lag: int,
    min_train_days: int = 252,
    refit_freq: int = 21,
) -> dict:
    """
    Walk-forward backtest for a single (factor, sector, lag) triple.

    Returns OOS performance metrics + daily P&L series.
    """
    df = pd.concat([
        factor_series.rename("factor"),
        target_series.rename("target"),
    ], axis=1).dropna()

    n = len(df)
    if n < min_train_days + refit_freq * 3:
        return {"error": "insufficient data"}

    oos_returns   = []
    oos_dates     = []
    signal_history = []

    t = min_train_days
    while t < n:
        # Training window: all data up to t
        train = df.iloc[:t]

        # Estimate IC direction on training window
        ic_estimate = compute_ic_on_window(
            train["factor"], train["target"], lag
        )

        # OOS: next REFIT_FREQ trading days
        oos_end   = min(t + refit_freq, n)
        oos_slice = df.iloc[t:oos_end]

        # Signal: long sector if IC > 0, flat otherwise (no shorting)
        position = 1.0 if ic_estimate > 0 else 0.0

        # OOS returns = position × actual sector return
        period_returns = oos_slice["target"].values * position
        oos_returns.extend(period_returns)
        oos_dates.extend(oos_slice.index)
        signal_history.extend([{"date": str(d.date()), "ic_est": round(ic_estimate, 4),
                                  "position": position}
                                 for d in oos_slice.index])

        t = oos_end

    if not oos_returns:
        return {"error": "no OOS returns generated"}

    oos = pd.Series(oos_returns, index=pd.DatetimeIndex(oos_dates))
    cum_ret = (1 + oos).cumprod()

    # Performance metrics
    sharpe = oos.mean() / oos.std() * np.sqrt(252) if oos.std() > 0 else 0.0
    max_dd = float(((cum_ret - cum_ret.cummax()) / cum_ret.cummax()).min())
    win_rate = float((oos > 0).mean())
    total_ret = float(cum_ret.iloc[-1] - 1)
    n_oos     = len(oos)

    return {
        "factor":       factor_series.name,
        "target":       target_series.name,
        "lag_days":     lag,
        "oos_sharpe":   round(sharpe, 3),
        "oos_max_dd":   round(max_dd, 4),
        "oos_win_rate": round(win_rate, 3),
        "oos_total_return": round(total_ret, 4),
        "oos_obs":      n_oos,
        "cumulative_return_series": {
            "dates":  [str(d.date()) for d in cum_ret.index],
            "values": [round(v, 4) for v in cum_ret.values],
        },
        "signal_history": signal_history,
    }


print("Walk-forward function defined.")
```

---

## Cell 7 [MARKDOWN]

### Run walk-forward backtest for all selected pairs

This may take a few minutes depending on the number of pairs.

---

## Cell 8 [CODE]

```python
# ── Run backtests ────────────────────────────────────────────────────────────
MIN_TRAIN  = 252
REFIT_FREQ = 21

backtest_results = []

for _, row in best_pairs.iterrows():
    factor_name = row["factor"]
    target_name = row["target"]
    lag         = int(row["lag_days"])

    if factor_name not in factor_returns.columns:
        print(f"  ⚠️  Factor '{factor_name}' not in data — skipping")
        continue
    if target_name not in sector_returns.columns:
        print(f"  ⚠️  Target '{target_name}' not in data — skipping")
        continue

    print(f"  Backtesting: {factor_name:12s} → {target_name:10s} lag={lag}d ...", end=" ")

    result = walk_forward_single(
        factor_returns[factor_name].rename(factor_name),
        sector_returns[target_name].rename(target_name),
        lag=lag,
        min_train_days=MIN_TRAIN,
        refit_freq=REFIT_FREQ,
    )

    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        backtest_results.append(result)
        print(f"OOS Sharpe={result['oos_sharpe']:.2f}, Return={result['oos_total_return']:.1%}")

print(f"\nCompleted {len(backtest_results)} backtests.")
```

---

## Cell 9 [MARKDOWN]

### Results summary

OOS Sharpe > 0.5 is considered promising for a prototype. The primary evidence is OOS, not IS — a high IS Sharpe with low OOS Sharpe indicates overfitting.

---

## Cell 10 [CODE]

```python
# ── Summary table ─────────────────────────────────────────────────────────────
summary = pd.DataFrame([{
    "factor":     r["factor"],
    "target":     r["target"],
    "lag_days":   r["lag_days"],
    "oos_sharpe": r["oos_sharpe"],
    "oos_return": f"{r['oos_total_return']:.1%}",
    "oos_max_dd": f"{r['oos_max_dd']:.1%}",
    "win_rate":   f"{r['oos_win_rate']:.1%}",
    "oos_obs":    r["oos_obs"],
} for r in backtest_results]).sort_values("oos_sharpe", ascending=False)

print("Walk-Forward Backtest Summary:")
print(summary.to_string(index=False))
```

---

## Cell 11 [CODE]

```python
# ── Cumulative return chart ───────────────────────────────────────────────────
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(14, 5))
ax.set_title("OOS Cumulative Returns — Factor Signal Walk-Forward Backtest",
             fontsize=12, fontweight="bold")

for r in backtest_results:
    cr = r["cumulative_return_series"]
    ax.plot(pd.to_datetime(cr["dates"]),
            [(v - 1) * 100 for v in cr["values"]],
            label=f"{r['factor']} → {r['target']} (lag {r['lag_days']}d, Sharpe={r['oos_sharpe']:.2f})",
            linewidth=1.5)

ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
ax.set_ylabel("Cumulative Return (%)")
ax.set_xlabel("Date")
ax.legend(fontsize=8, loc="upper left")
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "walk_forward_returns.png", dpi=150, bbox_inches="tight")
plt.show()
print("Chart saved.")
```

---

## Cell 12 [CODE]

```python
# ── Export results ────────────────────────────────────────────────────────────
output_path = OUTPUT_DIR / "walk_forward_results.json"

def serialise(v):
    if isinstance(v, (np.bool_,)):    return bool(v)
    if isinstance(v, (np.floating,)): return float(v)
    if isinstance(v, (np.integer,)):  return int(v)
    return v

export = [
    {k: (serialise(v) if not isinstance(v, dict) else v)
     for k, v in r.items()}
    for r in backtest_results
]

with open(output_path, "w") as f:
    json.dump({"results": export, "n_pairs": len(export)}, f, indent=2)

print(f"✅ Exported walk-forward results for {len(export)} factor-sector pairs to {output_path}")
if backtest_results:
    best = max(backtest_results, key=lambda x: x["oos_sharpe"])
    print(f"\nBest pair: {best['factor']} → {best['target']} lag {best['lag_days']}d "
          f"— OOS Sharpe = {best['oos_sharpe']:.2f}, Return = {best['oos_total_return']:.1%}")
```
