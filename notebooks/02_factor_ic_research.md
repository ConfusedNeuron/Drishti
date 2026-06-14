# Notebook 02 — Factor IC Research
> Run in: **BQuant (Bloomberg hosted Python environment at FRTL)**
> Inputs: `equities_returns.parquet`, `sector_returns.parquet`, `commodity_returns.parquet`, `macro_series.parquet` (from Notebook 01)
> Output artifact: `factor_ic_results.json`

---


# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti researches how commodity and macro shocks transmit risk into Indian equity sectors. This notebook is part of the quantitative factor research layer, which tests whether commodity return signals have predictive power over sector index returns — the statistical foundation for the portfolio's commodity exposure assessment.

The research findings feed directly into the Drishti dashboard's *Factor Research* panel, which shows which commodity factors have historically led sector returns and by how many days.

---


## Notebook 02 — Factor IC Research

**What this notebook does:**

Computes the **Information Coefficient (IC)** for each (commodity factor, sector target, lag) combination. IC measures the time-series predictive relationship between a lagged factor return and a forward sector return.

**Important specification note:**
A single commodity return at time t is a *scalar* — identical across all stocks. Standard cross-sectional IC (rank-correlating a scalar with a cross-section of stock returns) is therefore undefined or trivially zero. We use **time-series IC** instead: the rolling Pearson correlation between `factor_{t-lag}` and `target_t` over a 63-trading-day window, averaged over the sample.

**Metrics computed per (factor, sector, lag) triple:**
| Metric | Definition | Significance threshold |
|--------|-----------|----------------------|
| IC mean | Mean of rolling 63-day Pearson correlations | >0.05 economically meaningful |
| IC std | Standard deviation of rolling IC | — |
| ICIR | IC mean / IC std | >0.5 consistent; >1.0 strong |
| t-stat | ICIR × √n_periods | \|t\| > 1.96 at 5%; > 2.58 at 1% |
| p-value | Two-tailed from t-distribution | — |
| BH significant | Benjamini-Hochberg FDR correction (α=0.05) | Controls false discoveries across all tests |

**Lags tested:** 1, 2, 3, 5, 10 trading days

**Factors:** brent, wti, gold, copper, natgas, usdinr, gsec10y

**Targets:** energy, metals, fmcg, it sector indices

---


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
OUTPUT_DIR = INPUT_DIR   # artifacts saved to same location

print("Loading data from Notebook 01 exports...")
```

---


```python
# ── Load data ───────────────────────────────────────────────────────────────
sector_returns    = pd.read_parquet(INPUT_DIR / "sector_returns.parquet")
commodity_returns = pd.read_parquet(INPUT_DIR / "commodity_returns.parquet")
macro_returns     = pd.read_parquet(INPUT_DIR / "macro_series.parquet")

# Combine commodity + macro into a single factor DataFrame
# gsec10y is a yield change (not pct return) — already handled in notebook 01
factor_returns = pd.concat([commodity_returns, macro_returns], axis=1)

# Align on common dates
common_idx = sector_returns.index.intersection(factor_returns.index)
sector_returns = sector_returns.loc[common_idx]
factor_returns = factor_returns.loc[common_idx]

print(f"Factors:  {list(factor_returns.columns)}")
print(f"Targets:  {list(sector_returns.columns)}")
print(f"Observations: {len(common_idx)} trading days")
```

---


### IC computation — rolling Pearson correlation

For each (factor, target, lag) triple:
1. Shift factor by `lag` days backward (so `factor_shifted[t] = factor[t - lag]`).
2. Compute rolling 63-day Pearson correlation between `factor_shifted` and `target`.
3. Report the mean, std, and t-stat of this IC time series.

A 63-day window ≈ 1 quarter of trading days — long enough for stable correlation estimates but short enough to capture regime changes.

---


```python
# ── Core IC function ─────────────────────────────────────────────────────────

def compute_ic(
    factor: pd.Series,
    target: pd.Series,
    lag: int,
    rolling_window: int = 63,
) -> dict:
    """
    Time-series IC: rolling Pearson correlation between lagged factor and target.

    Parameters
    ----------
    factor : daily return series of the commodity/macro factor
    target : daily return series of the sector index
    lag    : how many trading days the factor leads the target
    rolling_window : window for rolling correlation (63 ≈ 1 quarter)

    Returns
    -------
    dict with ic_mean, ic_std, icir, t_stat, p_value, n_periods
    """
    # Align series on common dates
    df = pd.concat([factor.rename("f"), target.rename("t")], axis=1).dropna()

    # Shift factor: factor at t-lag predicts target at t
    df["f_lagged"] = df["f"].shift(lag)
    df = df.dropna()

    if len(df) < rolling_window + lag + 10:
        return None   # insufficient data

    # Rolling Pearson correlation
    ic_series = df["f_lagged"].rolling(rolling_window).corr(df["t"]).dropna()

    n          = len(ic_series)
    ic_mean    = float(ic_series.mean())
    ic_std     = float(ic_series.std())
    icir       = ic_mean / ic_std if ic_std > 0 else 0.0
    t_stat     = icir * np.sqrt(n)
    p_value    = float(2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1)))
    pct_pos    = float((ic_series > 0).mean())

    return {
        "factor":     factor.name,
        "target":     target.name,
        "lag_days":   lag,
        "ic_mean":    round(ic_mean, 4),
        "ic_std":     round(ic_std, 4),
        "icir":       round(icir, 3),
        "t_stat":     round(t_stat, 3),
        "p_value":    round(p_value, 4),
        "pct_positive": round(pct_pos, 3),
        "n_periods":  n,
        "significant": abs(t_stat) > 1.96,
        "bh_significant": False,   # filled in below after BH correction
    }


print("IC function defined.")
```

---


### Run IC for all (factor, target, lag) combinations

With 7 factors × 4 sector targets × 5 lags = 140 tests. Without multiple-testing correction, several results will appear significant by chance at the 5% level (~7 false discoveries expected). We apply Benjamini-Hochberg FDR correction afterward.

---


```python
# ── Run all (factor, target, lag) combinations ───────────────────────────────
LAGS = [1, 2, 3, 5, 10]

results = []
for factor_name in factor_returns.columns:
    for target_name in sector_returns.columns:
        for lag in LAGS:
            row = compute_ic(
                factor_returns[factor_name].rename(factor_name),
                sector_returns[target_name].rename(target_name),
                lag=lag,
            )
            if row is not None:
                results.append(row)

print(f"Total (factor, target, lag) combinations tested: {len(results)}")
print(f"Significant at 5% (uncorrected): {sum(r['significant'] for r in results)}")
```

---


### Benjamini-Hochberg FDR correction

With 140 tests and α=0.05, we expect ~7 false discoveries by chance. BH controls the **false discovery rate** (expected fraction of rejections that are false positives) rather than the family-wise error rate. It is less conservative than Bonferroni while still controlling FDR at 5%.

**BH procedure:**
1. Sort p-values ascending: p_(1) ≤ p_(2) ≤ … ≤ p_(m)
2. Find the largest k such that p_(k) ≤ k × α / m
3. Reject all hypotheses with rank ≤ k

---


```python
# ── Benjamini-Hochberg FDR correction ────────────────────────────────────────

def bh_correction(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """
    Returns boolean mask: True = reject H0 after BH correction.
    """
    n          = len(p_values)
    sorted_idx = np.argsort(p_values)
    sorted_p   = p_values[sorted_idx]
    thresholds = np.arange(1, n + 1) * alpha / n
    below      = sorted_p <= thresholds

    discoveries = np.zeros(n, dtype=bool)
    if below.any():
        max_k = int(np.where(below)[0][-1])
        discoveries[sorted_idx[:max_k + 1]] = True

    return discoveries


p_vals  = np.array([r["p_value"] for r in results])
bh_mask = bh_correction(p_vals, alpha=0.05)

for i, r in enumerate(results):
    r["bh_significant"] = bool(bh_mask[i])

n_bh = sum(r["bh_significant"] for r in results)
print(f"Significant after BH correction (FDR ≤ 5%): {n_bh} / {len(results)}")
```

---


### Results table — top factor-lag pairs

Ranked by |t-stat|. The BH column indicates whether the finding survives multiple-testing correction. Focus on BH-significant results for interpretation — others may be noise.

---


```python
# ── Display results ───────────────────────────────────────────────────────────
ic_df = pd.DataFrame(results).sort_values("t_stat", key=abs, ascending=False)

# Display top 20
display_cols = ["factor", "target", "lag_days", "ic_mean", "icir",
                "t_stat", "p_value", "pct_positive", "significant", "bh_significant"]

print("Top 20 factor-lag pairs by |t-stat|:")
print(ic_df[display_cols].head(20).to_string(index=False))

print(f"\nBH-significant factor-lag pairs:")
bh_sig = ic_df[ic_df["bh_significant"]]
print(bh_sig[display_cols].to_string(index=False))
```

---


### IC profile chart — best lag per factor

For the top 3 factors (by |t-stat|), plot IC mean across all lags. A clean lag profile (peak at one lag, declining at others) provides economic confirmation — e.g., Brent crude peaking at lag 2 is consistent with a 2-day transmission from global crude price to refinery margins and stock prices.

---


```python
# ── IC lag profile for top factors ──────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# Identify top 3 factors by mean |t-stat| across all targets and lags
factor_rank = (
    ic_df.groupby("factor")["t_stat"]
    .apply(lambda x: x.abs().mean())
    .sort_values(ascending=False)
)
top_factors = factor_rank.head(3).index.tolist()

fig, axes = plt.subplots(1, len(top_factors), figsize=(14, 4), sharey=False)
fig.suptitle("IC Mean by Lag — Top Factors", fontsize=13, fontweight="bold")

for ax, factor_name in zip(axes, top_factors):
    sub = ic_df[ic_df["factor"] == factor_name]

    for target_name, grp in sub.groupby("target"):
        ax.plot(grp["lag_days"], grp["ic_mean"],
                marker="o", label=target_name)

    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.axhline(0.05, color="green", linewidth=0.8, linestyle=":",
               label="IC=0.05 threshold")
    ax.set_title(factor_name.upper())
    ax.set_xlabel("Lag (trading days)")
    ax.set_ylabel("IC Mean")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "ic_lag_profiles.png", dpi=150, bbox_inches="tight")
plt.show()
print("Chart saved.")
```

---


```python
# ── Export results ────────────────────────────────────────────────────────────
output_path = OUTPUT_DIR / "factor_ic_results.json"

# Convert to list of dicts with serializable types
export = [
    {k: (bool(v) if isinstance(v, (np.bool_,)) else
         float(v) if isinstance(v, (np.floating,)) else
         int(v)  if isinstance(v, (np.integer,)) else v)
     for k, v in r.items()}
    for r in results
]

with open(output_path, "w") as f:
    json.dump({"results": export, "n_tests": len(export)}, f, indent=2)

print(f"✅ Exported {len(export)} IC results to {output_path}")
print(f"\nTop result:")
top = ic_df.iloc[0]
print(f"  {top['factor']} → {top['target']} at lag {top['lag_days']}d: "
      f"IC={top['ic_mean']:.3f}, t={top['t_stat']:.2f}, "
      f"BH={'Yes' if top['bh_significant'] else 'No'}")
```
