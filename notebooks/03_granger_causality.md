# Notebook 03 — Granger Causality
> Run in: **BQuant (Bloomberg hosted Python environment at FRTL)**
> Inputs: `sector_returns.parquet`, `commodity_returns.parquet`, `macro_series.parquet` (from Notebook 01)
> Output artifact: `granger_results.json`

---


# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti is a local-first quantitative risk research platform for Indian equity portfolios. The research pipeline tests how commodity and macro shocks transmit risk into Indian equity sectors using methodologies standard in the Indian equity-commodity literature: Diebold-Yilmaz connectedness, DCC-GARCH dynamic correlations, and VAR-based lead-lag analysis.

The assigned reading (Mukherjee-Bardhan gold spillover paper) uses a VAR-MGARCH/DCC framework. This notebook implements the Granger causality component — the statistical test that asks whether lagged commodity returns improve prediction of sector returns beyond the sector's own history.

---


## Notebook 03 — Granger Causality

**What this notebook does:**

Tests **Granger causality** from each commodity/macro factor to each sector index. Granger causality answers: *"Does knowing the past history of X improve our forecast of Y beyond Y's own past?"*

**Method:** VAR-based Granger causality (Granger, 1969; Sims, 1980).
For each (factor X, sector Y) pair:
- Fit a restricted VAR: Y regressed on own lags only
- Fit an unrestricted VAR: Y regressed on own lags + lagged X
- F-test for the joint significance of X's lagged coefficients

**Test for each pair:** lags 1 through 10 (up to 2 trading weeks)

**Interpretation:**
- Significant (p < 0.05): past factor returns have incremental predictive power for sector returns beyond the sector's own history
- Not significant: does not mean no relationship — only that the relationship is not detectable in this linear VAR framework

**Multiple testing:** Benjamini-Hochberg FDR correction applied across all (factor, sector, lag) combinations.

**This complements IC:** IC measures the strength and direction of the lead-lag signal; Granger tests its statistical significance in a VAR framework that controls for the sector's own autocorrelation.

---


```python
# ── Imports ────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests, adfuller
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

INPUT_DIR  = Path("/bquant/data/drishti")
OUTPUT_DIR = INPUT_DIR

print("Loading data from Notebook 01 exports...")
```

---


```python
# ── Load data ────────────────────────────────────────────────────────────────
sector_returns    = pd.read_parquet(INPUT_DIR / "sector_returns.parquet")
commodity_returns = pd.read_parquet(INPUT_DIR / "commodity_returns.parquet")
macro_returns     = pd.read_parquet(INPUT_DIR / "macro_series.parquet")

factor_returns = pd.concat([commodity_returns, macro_returns], axis=1)

common_idx = sector_returns.index.intersection(factor_returns.index)
sector_returns = sector_returns.loc[common_idx]
factor_returns = factor_returns.loc[common_idx]

print(f"Factors:  {list(factor_returns.columns)}")
print(f"Targets:  {list(sector_returns.columns)}")
print(f"Observations: {len(common_idx)} trading days")
```

---


### Stationarity check (ADF test)

Granger causality tests assume stationary series. Daily *returns* are generally stationary (unlike price *levels*). We verify this with the Augmented Dickey-Fuller test. If any series fails the test (p > 0.05, cannot reject unit root), we difference it.

---


```python
# ── ADF stationarity test ────────────────────────────────────────────────────

def adf_test(series: pd.Series, name: str) -> bool:
    """
    Augmented Dickey-Fuller test.
    H0: series has a unit root (non-stationary).
    Returns True if stationary (reject H0 at 5%).
    """
    result = adfuller(series.dropna(), autolag="AIC")
    p_val  = result[1]
    is_stationary = p_val < 0.05
    status = "✅ stationary" if is_stationary else "⚠️  NON-STATIONARY"
    print(f"  {name:20s}  p={p_val:.4f}  {status}")
    return is_stationary

print("ADF test — sector returns:")
for col in sector_returns.columns:
    adf_test(sector_returns[col], col)

print("\nADF test — factor returns:")
for col in factor_returns.columns:
    adf_test(factor_returns[col], col)
```

---


### Granger causality test function

For each (factor, sector) pair, `statsmodels.grangercausalitytests` fits both restricted and unrestricted VARs at each lag order 1 to `max_lag` and reports the F-statistic and p-value from the SSR F-test. We report all lags so the lag profile can be inspected visually.

---


```python
# ── Granger causality function ────────────────────────────────────────────────

def run_granger(
    factor: pd.Series,
    target: pd.Series,
    max_lag: int = 10,
) -> list[dict]:
    """
    Run Granger causality test (factor → target) at lags 1 to max_lag.

    Returns list of dicts, one per lag, with F-stat and p-value.
    Uses the SSR F-test (more robust than chi-squared for small samples).
    """
    factor_name = factor.name
    target_name = target.name

    # Build bivariate DataFrame: [target, factor] — statsmodels convention
    # is that the second column is the potential Granger cause of the first
    df = pd.concat([target.rename("target"),
                    factor.rename("factor")], axis=1).dropna()

    if len(df) < max_lag * 5 + 20:
        return []

    try:
        gc = grangercausalitytests(df.values, maxlag=max_lag, verbose=False)
    except Exception as e:
        print(f"  Skipped {factor_name}→{target_name}: {e}")
        return []

    results = []
    for lag in range(1, max_lag + 1):
        # SSR F-test: more reliable with moderate sample sizes
        f_stat = float(gc[lag][0]["ssr_ftest"][0])
        p_val  = float(gc[lag][0]["ssr_ftest"][1])
        results.append({
            "factor":      factor_name,
            "target":      target_name,
            "lag":         lag,
            "f_stat":      round(f_stat, 4),
            "p_value":     round(p_val, 4),
            "significant": p_val < 0.05,
            "bh_significant": False,   # filled after BH correction
        })
    return results


print("Granger causality function defined.")
```

---


### Run all (factor, sector) pairs

7 factors × 4 sector targets × 10 lags = 280 tests. BH correction will be applied across all p-values.

---


```python
# ── Run all Granger tests ─────────────────────────────────────────────────────
MAX_LAG = 10
all_results = []

for factor_name in factor_returns.columns:
    for target_name in sector_returns.columns:
        print(f"  Testing: {factor_name:12s} → {target_name:10s} ...", end=" ")
        pair_results = run_granger(
            factor_returns[factor_name].rename(factor_name),
            sector_returns[target_name].rename(target_name),
            max_lag=MAX_LAG,
        )
        all_results.extend(pair_results)
        n_sig = sum(r["significant"] for r in pair_results)
        print(f"{n_sig}/{MAX_LAG} lags significant")

print(f"\nTotal tests: {len(all_results)}")
print(f"Significant (uncorrected, p<0.05): {sum(r['significant'] for r in all_results)}")
```

---


```python
# ── Benjamini-Hochberg FDR correction ────────────────────────────────────────

def bh_correction(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
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

p_vals  = np.array([r["p_value"] for r in all_results])
bh_mask = bh_correction(p_vals, alpha=0.05)

for i, r in enumerate(all_results):
    r["bh_significant"] = bool(bh_mask[i])

print(f"BH-significant (FDR ≤ 5%): {sum(r['bh_significant'] for r in all_results)} / {len(all_results)}")
```

---


### Results: Granger causality matrix

Summarise the minimum p-value across all lags for each (factor, sector) pair, and the lag at which it occurs. This gives the "best lag" at which each factor Granger-causes each sector.

---


```python
# ── Granger causality summary matrix ─────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

gc_df = pd.DataFrame(all_results)

# For each (factor, sector) pair: find the lag with the minimum p-value
best_lag_df = (
    gc_df.sort_values("p_value")
    .groupby(["factor", "target"])
    .first()
    .reset_index()
    [["factor", "target", "lag", "f_stat", "p_value", "bh_significant"]]
)

# Pivot for heatmap: rows = factors, columns = sectors, values = min p-value
pivot = best_lag_df.pivot(index="factor", columns="target", values="p_value")

fig, ax = plt.subplots(figsize=(8, 5))
cmap = plt.cm.RdYlGn_r   # red = low p-value (significant), green = high
im = ax.imshow(pivot.values, cmap=cmap, vmin=0, vmax=0.2, aspect="auto")

ax.set_xticks(range(len(pivot.columns)))
ax.set_yticks(range(len(pivot.index)))
ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
ax.set_yticklabels(pivot.index)

# Annotate with p-values
for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):
        val = pivot.values[i, j]
        if not np.isnan(val):
            text = f"{val:.3f}"
            color = "white" if val < 0.05 else "black"
            ax.text(j, i, text, ha="center", va="center",
                    fontsize=9, color=color, fontweight="bold" if val < 0.05 else "normal")

ax.set_title("Granger Causality — Min p-value across lags 1–10\n(red = strong evidence)", fontsize=11)
plt.colorbar(im, ax=ax, label="p-value (min across lags)")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "granger_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Heatmap saved.")
```

---


```python
# ── Display best-lag summary ─────────────────────────────────────────────────
print("\nBest-lag summary (min p-value per factor-sector pair):")
print(best_lag_df.sort_values("p_value").to_string(index=False))
```

---


```python
# ── Export results ────────────────────────────────────────────────────────────
output_path = OUTPUT_DIR / "granger_results.json"

def serialise(v):
    if isinstance(v, (np.bool_,)):    return bool(v)
    if isinstance(v, (np.floating,)): return float(v)
    if isinstance(v, (np.integer,)):  return int(v)
    return v

export = [{k: serialise(v) for k, v in r.items()} for r in all_results]

with open(output_path, "w") as f:
    json.dump({"results": export, "n_tests": len(export)}, f, indent=2)

print(f"✅ Exported {len(export)} Granger test results to {output_path}")
```
