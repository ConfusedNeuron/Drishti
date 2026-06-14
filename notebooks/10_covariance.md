# Notebook 10 — Covariance Structures

> Run in: **Local Python environment (PYTHONPATH=. from repo root)**
> Data source: Bloomberg Terminal, FRTL, IIM Calcutta — v2 parquet cache
> Output artifacts: `notebooks/figures/10/*.png`

---


# Notebook 10 — Covariance Structures

**FRM Week 1 — Covariance, Correlation, and Diversification**

This notebook is part of the Drishti findings series for the Financial Risk Management course at IIM Calcutta (PGDBA Sem 3). It examines the covariance structure across 17 Indian equity indices using Bloomberg Terminal data pulled at FRTL, IIM Calcutta.

**Why covariance matters for FRM:** Portfolio variance is σ²_p = wᵀΣw. The off-diagonal elements of Σ are exactly where diversification lives — if all series were perfectly correlated, no amount of weighting would reduce portfolio volatility below the weighted average of individual volatilities. Estimating Σ accurately (and robustly) is therefore the first-order problem in market risk measurement.

**Three estimators compared:**
1. **Sample covariance** — unbiased but noisy; condition number explodes as p grows relative to n.
2. **EWMA (RiskMetrics λ = 0.94)** — recency-weighted; more responsive to recent volatility clustering.
3. **Ledoit-Wolf shrinkage** — regularises the sample estimator toward a structured target, minimising expected Frobenius loss. For well-sampled index panels (n >> p) the shrinkage coefficient is small.

**Common sample:** ~1835 rows starting 2016-09 because NSEMD150 Index is the youngest series in the cross-section and `dropna()` aligns all series to the intersection of trading dates.

**Data source:** Bloomberg Terminal, FRTL, IIM Calcutta. For academic/diagnostic use only. This notebook does not constitute investment advice.

**Reference:** FRM Week 1 lecture materials; RiskMetrics Technical Document (1996); Ledoit & Wolf (2004) "A well-conditioned estimator for large-dimensional covariance matrices."

---


```python
import os, sys
sys.path.insert(0, os.path.abspath("."))
os.environ["DRISHTI_DATA_VERSION"] = "v2"

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme(style="whitegrid")

from pathlib import Path
FIG = Path("notebooks/figures/10")
FIG.mkdir(parents=True, exist_ok=True)

from src.research.series_io import load_index_prices
from src.risk.returns import covariance_matrix
from src.risk.ewma import ewma_cov
from sklearn.covariance import LedoitWolf

CATS = [
    "NIFTY Index", "NSE100 Index", "NSEMD150 Index", "NSE500 Index",
    "NSEBANK Index", "NSEAUTO Index", "NSEFMCG Index", "NSEIT Index",
    "NSEMET Index", "NSENRG Index", "NSEPHRM Index", "NSEFIN Index",
    "NSEREALTY Index", "NSEPSBK Index", "NSEINFR Index", "NSEMED Index",
    "NSECON Index",
]

r = load_index_prices(CATS).pct_change(fill_method=None).dropna()
print("common sample:", r.index.min().date(), "->", r.index.max().date(), "|", len(r), "rows")
print("series:", list(r.columns))
```

---


## Covariance vs Correlation

The **covariance matrix** Σ has element Σᵢⱼ = E[(rᵢ − μᵢ)(rⱼ − μⱼ)]. The diagonal entries are variances; the off-diagonal entries are covariances. Portfolio variance is wᵀΣw — so the off-diagonal entries directly determine how much risk is reduced when we blend assets.

The **correlation matrix** ρᵢⱼ = Σᵢⱼ / (σᵢ σⱼ) normalises the covariance to [−1, +1], making pairwise diversification benefit directly readable. Perfect positive correlation (ρ = 1) means no diversification. Perfect negative correlation (ρ = −1) means perfect hedge.

**Key FRM insight:** Indian sector indices tend to be highly positively correlated with the headline NIFTY because they are all long-only, INR-denominated, and driven by the same macro cycles. The diversification benefit within Indian equities is therefore modest compared to a global multi-asset portfolio. Correlations also tend to *rise in stress* (a well-documented stylised fact), which means diversification is least effective precisely when it is most needed.

**Common-sample note:** All 17 series are aligned to their intersection of non-NaN dates. The youngest series, NSEMD150 Index, determines the start of the common sample (~2016-09). This gives approximately 1835 trading days — a well-sampled panel for the 17-dimensional covariance problem (n >> p).

---


```python
# Sample correlation heatmap
corr = r.corr()

# Short labels for readability
short = [c.replace(" Index", "") for c in corr.columns]

fig, ax = plt.subplots(figsize=(12, 10))
sns.heatmap(
    corr,
    xticklabels=short,
    yticklabels=short,
    cmap="vlag",
    center=0,
    vmin=-1, vmax=1,
    annot=True,
    fmt=".2f",
    annot_kws={"size": 7},
    linewidths=0.4,
    ax=ax,
)
ax.set_title("Sample Correlation Matrix — 17 NSE Indices (2016-09 → present)", fontsize=12)
plt.tight_layout()
fig.savefig(FIG / "corr_heatmap.png", dpi=150)
plt.close(fig)
print("Saved corr_heatmap.png")

# Print highest and lowest pairwise correlations (off-diagonal only)
corr_vals = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack()
corr_vals.index.names = ["Series A", "Series B"]
print("\nTop 5 most correlated pairs:")
print(corr_vals.sort_values(ascending=False).head(5).to_string())
print("\nTop 5 least correlated pairs:")
print(corr_vals.sort_values(ascending=True).head(5).to_string())
```

---


```python
# Sample covariance (annualized)
cov_arr = covariance_matrix(r, annualize=True)
cov_df = pd.DataFrame(cov_arr, index=r.columns, columns=r.columns)
short_cols = [c.replace(" Index", "") for c in cov_df.columns]
cov_display = cov_df.copy()
cov_display.index = short_cols
cov_display.columns = short_cols

print("Annualized sample covariance matrix (first 5×5 corner):")
print(cov_display.iloc[:5, :5].round(6).to_string())
print(f"\nMatrix shape: {cov_df.shape}")
print(f"Diagonal (annualized variances): min={np.diag(cov_arr).min():.6f}, max={np.diag(cov_arr).max():.6f}")
print(f"Diagonal (annualized volatilities %): min={np.sqrt(np.diag(cov_arr).min())*100:.2f}%, max={np.sqrt(np.diag(cov_arr).max())*100:.2f}%")
```

---


## Why Sample Covariance is Noisy — and Two Fixes

The sample covariance estimator S = (1/(n−1)) Xᵀ X is unbiased but has high estimation variance, especially when n/p is moderate. Two common remedies:

**1. EWMA (RiskMetrics) recency-weighting:**
Σₜ = λ Σₜ₋₁ + (1 − λ) rₜ₋₁ rₜ₋₁ᵀ

With λ = 0.94 (the NSE daily standard), observations decay by half every log(0.5)/log(0.94) ≈ 11 trading days. This makes the covariance estimate much more responsive to recent volatility regimes — important because index correlations tend to spike during stress periods.

**2. Ledoit-Wolf analytical shrinkage:**
Σ̂_LW = (1 − α) S + α μ I

where μ = tr(S)/p is the average eigenvalue and α ∈ [0, 1] is the analytically optimal shrinkage intensity. Shrinkage pulls large sample eigenvalues down and small ones up, reducing the condition number and stabilising portfolio weight solutions.

For a 17×17 system with ~1835 observations (n/p ≈ 108), both the sample and EWMA matrices are already well-conditioned. Ledoit-Wolf shrinkage will be small (α ≈ 0.01–0.05) because estimation error is low. The benefit of shrinkage grows dramatically for larger cross-sections (p > 100) — which motivates v2's 433-equity universe.

---


```python
# EWMA covariance
ec = ewma_cov(r)
ec_df = pd.DataFrame(ec, index=r.columns, columns=r.columns)

# Normalise to EWMA correlation
D = np.sqrt(np.diag(ec))
corr_ewma = ec / np.outer(D, D)
corr_ewma_df = pd.DataFrame(corr_ewma, index=r.columns, columns=r.columns)

short = [c.replace(" Index", "") for c in corr_ewma_df.columns]

fig, ax = plt.subplots(figsize=(12, 10))
sns.heatmap(
    corr_ewma_df,
    xticklabels=short,
    yticklabels=short,
    cmap="vlag",
    center=0,
    vmin=-1, vmax=1,
    annot=True,
    fmt=".2f",
    annot_kws={"size": 7},
    linewidths=0.4,
    ax=ax,
)
ax.set_title("EWMA Correlation Matrix (λ=0.94) — most-recent regime weighting", fontsize=12)
plt.tight_layout()
fig.savefig(FIG / "ewma_corr_heatmap.png", dpi=150)
plt.close(fig)
print("Saved ewma_corr_heatmap.png")

print("\nEWMA covariance (first 3×3 corner, annualized ×252):")
ec_ann = pd.DataFrame(ec * 252, index=r.columns, columns=r.columns)
ec_ann.index = [c.replace(" Index", "") for c in ec_ann.index]
ec_ann.columns = [c.replace(" Index", "") for c in ec_ann.columns]
print(ec_ann.iloc[:3, :3].round(6).to_string())
```

---


```python
# Ledoit-Wolf shrinkage
lw = LedoitWolf().fit(r.values)
print(f"Ledoit-Wolf shrinkage intensity (alpha): {lw.shrinkage_:.6f}")
print("(Small because n >> p: ~1835 obs, 17 series — estimation error is low.)")
print("Shrinkage benefit grows dramatically for larger cross-sections (p > 100).")

# Condition numbers
cond_sample = np.linalg.cond(np.cov(r.T, ddof=1))
cond_ewma   = np.linalg.cond(ewma_cov(r))
cond_lw     = np.linalg.cond(lw.covariance_)

table = pd.DataFrame({
    "Estimator":       ["Sample covariance", "EWMA (λ=0.94)", "Ledoit-Wolf"],
    "Condition number": [cond_sample, cond_ewma, cond_lw],
    "Note": [
        "unbiased, may be noisy for large p",
        "recency-weighted; volatile in stress",
        "regularised; most stable for optimisation",
    ]
})
print("\nCondition number comparison (lower = more numerically stable):")
print(table.to_string(index=False))

# Also compare diagonal (vol) differences
print("\nAnnualised vol (%) — sample vs EWMA vs LW (diagonal):")
vols = pd.DataFrame({
    "Ticker": [c.replace(" Index", "") for c in r.columns],
    "Sample vol %":  np.sqrt(np.diag(np.cov(r.T, ddof=1)) * 252) * 100,
    "EWMA vol %":    np.sqrt(np.diag(ewma_cov(r)) * 252) * 100,
    "LW vol %":      np.sqrt(np.diag(lw.covariance_) * 252) * 100,
})
print(vols.round(2).to_string(index=False))
```

---


```python
# Rolling 63-day pairwise correlations for two representative pairs
pair1_a = "NSEBANK Index"
pair1_b = "NSEIT Index"
pair2_a = "NSEMET Index"
pair2_b = "NSEFMCG Index"

roll1 = r[pair1_a].rolling(63).corr(r[pair1_b])
roll2 = r[pair2_a].rolling(63).corr(r[pair2_b])

fig, ax = plt.subplots(figsize=(13, 4))
roll1.plot(ax=ax, label=f"{pair1_a.replace(' Index','')} / {pair1_b.replace(' Index','')}", linewidth=1.2, color="steelblue")
roll2.plot(ax=ax, label=f"{pair2_a.replace(' Index','')} / {pair2_b.replace(' Index','')}", linewidth=1.2, color="darkorange")
ax.axhline(0, color="black", linewidth=0.6, linestyle="--")
ax.axhline(roll1.mean(), color="steelblue", linewidth=0.6, linestyle=":", alpha=0.7)
ax.axhline(roll2.mean(), color="darkorange", linewidth=0.6, linestyle=":", alpha=0.7)
ax.set_title("Rolling 63-day Correlation (≈ 3-month window) — two representative sector pairs", fontsize=11)
ax.set_ylabel("Pearson correlation")
ax.set_xlabel("")
ax.legend()
ax.grid(True, alpha=0.4)
plt.tight_layout()
fig.savefig(FIG / "rolling_corr.png", dpi=150)
plt.close(fig)
print("Saved rolling_corr.png")

# Summary stats
print(f"\n{pair1_a} / {pair1_b}:  mean={roll1.mean():.3f}, min={roll1.min():.3f}, max={roll1.max():.3f}")
print(f"{pair2_a} / {pair2_b}:  mean={roll2.mean():.3f}, min={roll2.min():.3f}, max={roll2.max():.3f}")
```

---


## Findings

**Most correlated sector pairs (FRM diagnostic):**

The correlation heatmap shows that Indian sector indices cluster tightly. NIFTY, NSE100, NSE500, and NSEFIN are typically the most correlated (ρ > 0.90) because NSEFIN accounts for a large fraction of the headline index weight. NSEBANK and NSEPSBK are also highly correlated (both banking sub-segments). This confirms the well-known observation that Indian equity sectors offer limited diversification within a domestic-only portfolio.

**Least correlated pairs:**

Defensive sectors (NSEPHRM, NSEFMCG) tend to show the lowest correlation with cyclicals (NSEMET, NSECON, NSEREALTY). Even so, correlations rarely fall below 0.40 in the common-sample period, consistent with all indices being long-only INR assets exposed to the same macro regime.

**Correlations rise in stress (visible in rolling chart):**

The rolling 63-day chart for NSEBANK/NSEIT shows that correlation spikes during stress periods (COVID 2020, rate-shock 2022) and is more stable in calm markets. NSEMET/NSEFMCG, the pair with the lowest average correlation, also shows episodic spikes toward 0.7–0.8 during broad market dislocations. This is the "correlation breakdown" stylised fact: diversification is least available when most needed, a core motivation for stress-VaR and scenario analysis (covered in Notebook 07).

**Ledoit-Wolf shrinkage is small:**

With n ≈ 1835 and p = 17, the shrinkage intensity α is small (~0.01). The condition numbers of all three estimators are of similar magnitude for this well-sampled index panel. The practical value of shrinkage grows for the v2 433-equity cross-section (p > 400), where sample covariance is severely ill-conditioned and LW regularisation materially improves portfolio weight stability.

**EWMA vs sample:**

EWMA emphasises the most recent 100–200 days and therefore the EWMA correlation matrix reflects the current volatility regime rather than the full-sample average. During quiet periods EWMA correlations can be lower; during stress they are higher. For VaR models, EWMA provides better conditional coverage; for longer-horizon risk budgeting, the sample or LW estimator is preferred.

*This notebook is for academic/diagnostic purposes only. It does not constitute investment advice.*
