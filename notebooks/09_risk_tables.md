# Notebook 09 — Variance-Based Risk & Risk-Adjusted Performance
> Run in: **Local machine**
> Data source: Bloomberg v2 cache (`data/cache/bloomberg_v2/`)
> Figures output: `notebooks/figures/09/`

---

## Cell 1 [MARKDOWN]

# Notebook 09 — Variance-Based Risk & Risk-Adjusted Performance

**FRM Wk1 — Risk as Variance and Diversification**

In the foundational week of Financial Risk Management, risk is defined in terms of the variance (or standard deviation) of returns. A higher variance means outcomes are more dispersed around the expected value, implying greater uncertainty. Diversification reduces portfolio variance by combining assets whose returns are less than perfectly correlated — the variance of a portfolio is strictly less than the weighted average of individual variances when correlations are below 1.

**FRM Wk3 — Risk-Adjusted Performance Measures**

Week 3 introduces the canonical measures that compare return earned relative to risk taken:

- **Sharpe Ratio** (Sharpe 1966): excess return over the risk-free rate, scaled by total volatility (standard deviation). Appropriate when the asset is the investor's entire portfolio.
- **Treynor Ratio** (Treynor 1965): excess return scaled by systematic risk (beta). Appropriate when the asset is one component of a diversified portfolio.
- **Jensen's Alpha** (Jensen 1968): annualized return in excess of what the CAPM predicts for the asset's systematic risk level. Positive alpha indicates outperformance on a risk-adjusted basis.

**Data source:** Bloomberg Terminal, FRTL, IIM Calcutta — daily prices for NSE indices and sector indices, 2006–2026-06-12.

**Diagnostic note:** This notebook is for educational and analytical purposes only. Nothing here constitutes investment advice or a recommendation to buy, sell, or hold any security or index.

---

## Cell 2 [CODE]

```python
import os, sys
sys.path.insert(0, os.path.abspath("."))
os.environ["DRISHTI_DATA_VERSION"] = "v2"
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style="whitegrid")
from pathlib import Path
FIG = Path("notebooks/figures/09"); FIG.mkdir(parents=True, exist_ok=True)
from src.research.series_io import load_index_prices, load_macro_prices
from src.risk.performance import sharpe, treynor, jensen_alpha, beta
INDEX_HEADLINES = ["NIFTY Index","NSE100 Index","NSEMD150 Index","NSE500 Index"]
SECTORS = ["NSEBANK Index","NSEAUTO Index","NSEFMCG Index","NSEIT Index","NSEMET Index","NSENRG Index","NSEPHRM Index","NSEFIN Index","NSEREALTY Index","NSEPSBK Index","NSEINFR Index","NSEMED Index","NSECON Index"]
CATS = INDEX_HEADLINES + SECTORS
print("Preamble loaded. CATS:", len(CATS), "tickers")
```

---

## Cell 3 [MARKDOWN]

## Risk = Variance of Returns

In the FRM framework (Week 1), risk is formally defined as the variance of portfolio returns:

$$\sigma^2_p = \mathbf{w}^\top \Sigma \mathbf{w}$$

where **w** is the vector of portfolio weights and **Σ** is the covariance matrix of asset returns. This definition captures both the magnitude of uncertainty and its directionality through covariances.

**Annualized variance and volatility** are the practical quantities reported below. We annualize by multiplying daily variance by 252 (trading days per year), giving:

- Annualized variance: $\hat{\sigma}^2_{\text{ann}} = \hat{\sigma}^2_{\text{daily}} \times 252$
- Annualized volatility: $\hat{\sigma}_{\text{ann}} = \hat{\sigma}_{\text{daily}} \times \sqrt{252}$

This allows comparison across indices and sectors on a common scale regardless of calendar differences.

---

## Cell 4 [CODE]

```python
# Load prices and compute daily returns
px = load_index_prices(CATS)
rets = px.pct_change(fill_method=None)

# Build risk table
rows = []
for cat in CATS:
    r = rets[cat].dropna()
    ann_var = float(r.var(ddof=1) * 252)
    ann_vol = float(r.std(ddof=1) * np.sqrt(252))
    rows.append({"Index / Sector": cat, "Ann. Variance": ann_var, "Ann. Volatility": ann_vol})

table = pd.DataFrame(rows).set_index("Index / Sector")
table = table.sort_values("Ann. Volatility", ascending=False)

print("=== Variance-Based Risk Table (sorted by Ann. Volatility, descending) ===")
print(table.round(4).to_string())

# Bar chart
fig, ax = plt.subplots(figsize=(12, 6))
labels = [c.replace(" Index", "") for c in table.index]
ax.barh(labels[::-1], table["Ann. Volatility"].values[::-1], color="#3891F0", edgecolor="white", linewidth=0.4)
ax.set_xlabel("Annualized Volatility", fontsize=12)
ax.set_title("Annualized Volatility by Index / Sector (Bloomberg v2, 2006–2026)", fontsize=13)
ax.axvline(table.loc["NIFTY Index", "Ann. Volatility"], color="#C9A227", linestyle="--", linewidth=1.2, label="NIFTY benchmark")
ax.legend(fontsize=10)
plt.tight_layout()
fig.savefig(FIG / "volatility_bar.png", dpi=150)
plt.close(fig)
print(f"\nFigure saved: {FIG}/volatility_bar.png")
```

---

## Cell 5 [MARKDOWN]

## Risk-Adjusted Performance

Raw returns are uninformative without accounting for the risk taken to earn them. FRM Week 3 introduces three complementary measures derived from CAPM:

**Sharpe Ratio:**
$$S_p = \frac{\bar{r}_p - r_f}{\sigma_p} \times \sqrt{T}$$
Uses total volatility $\sigma_p$ — relevant when the index is the sole investment.

**Treynor Ratio:**
$$T_p = \frac{\bar{r}_p^{\text{ann}} - r_f}{\beta_p}$$
Uses systematic risk $\beta_p$ relative to the market (NIFTY) — relevant when the index is held alongside other diversifying assets.

**Jensen's Alpha:**
$$\alpha_p = \bar{r}_p^{\text{ann}} - \left[r_f + \beta_p \left(\bar{r}_m^{\text{ann}} - r_f\right)\right]$$
Measures annualized outperformance versus the CAPM prediction. A positive $\alpha$ means the index earned more than its beta-adjusted cost of capital.

Risk-free rate: **GIND10YR Index** (India 10-year Government Bond yield, Bloomberg), converted from percent to decimal. Market proxy: **NIFTY 50**.

---

## Cell 6 [CODE]

```python
# Risk-free rate from Bloomberg India 10Y yield (stored in percent — must divide by 100)
rf_annual = float(load_macro_prices(['GIND10YR Index']).iloc[-1, 0]) / 100
print(f"Risk-free rate (rf_annual): {rf_annual:.5f}  ({rf_annual*100:.3f}%)")

# Market proxy: NIFTY daily returns
mkt = load_index_prices(['NIFTY Index'])['NIFTY Index'].pct_change(fill_method=None).dropna()

# Compute performance metrics for every category
perf_rows = []
for cat in CATS:
    r = rets[cat].dropna()
    s = sharpe(r, rf_annual)
    b = beta(r, mkt)
    tr = treynor(r, mkt, rf_annual)
    ja = jensen_alpha(r, mkt, rf_annual)
    perf_rows.append({
        "Index / Sector": cat,
        "Sharpe": s,
        "Beta": b,
        "Treynor": tr,
        "Jensen Alpha": ja,
    })

perf = pd.DataFrame(perf_rows).set_index("Index / Sector")
perf = perf.sort_values("Sharpe", ascending=False)

print("\n=== Risk-Adjusted Performance Table (sorted by Sharpe, descending) ===")
print(perf.round(3).to_string())
```

---

## Cell 7 [CODE]

```python
# Risk-return scatter: annualized mean return vs annualized volatility
ann_means = (rets[CATS].apply(lambda s: s.dropna().mean()) * 252).rename("Ann. Mean Return")
ann_vols = table["Ann. Volatility"]

fig, ax = plt.subplots(figsize=(11, 7))
ax.scatter(ann_vols, ann_means, color="#C9A227", s=70, zorder=3, edgecolors="white", linewidths=0.5)

for cat in CATS:
    label = cat.replace(" Index", "")
    x = ann_vols.get(cat, np.nan)
    y = ann_means.get(cat, np.nan)
    if np.isfinite(x) and np.isfinite(y):
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(5, 3),
                    fontsize=7.5, color="#333333")

# Add rf horizontal reference
ax.axhline(rf_annual, color="#DC4040", linestyle="--", linewidth=1.0, label=f"Risk-free rate ({rf_annual*100:.2f}%)")
ax.set_xlabel("Annualized Volatility", fontsize=12)
ax.set_ylabel("Annualized Mean Return", fontsize=12)
ax.set_title("Risk–Return Space: NSE Indices & Sectors (Bloomberg v2, 2006–2026)", fontsize=13)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.4)
plt.tight_layout()
fig.savefig(FIG / "risk_return_scatter.png", dpi=150)
plt.close(fig)
print(f"Figure saved: {FIG}/risk_return_scatter.png")
```

---

## Cell 8 [MARKDOWN]

## Findings

**Diagnostic observations — not investment advice.**

**Variance and volatility (FRM Wk1):**

The sector indices carry substantially more variance than the broad market indices. Real estate (NSEREALTY), energy (NSENRG), metals (NSEMET), and PSU banks (NSEPSBK) consistently appear near the top of the volatility ranking. This is consistent with sector concentration: concentrated sector exposures cannot diversify away industry-specific shocks, so per-unit volatility is higher than the blended NIFTY 50. The diversification benefit of the broad index (NIFTY, NSE100, NSE500) is directly visible as the gap between these indices and the highest-volatility sectors — this is the empirical demonstration of the Wk1 diversification principle in an Indian equity context.

**Risk-adjusted performance (FRM Wk3 — Sharpe / Treynor / Jensen):**

- The Sharpe ranking reveals which indices delivered the most return per unit of total risk. Broad indices (NIFTY, NSE100, NSE500) tend to cluster near the middle, reflecting their diversified composition.
- Beta values above 1.0 indicate higher systematic sensitivity than the NIFTY benchmark — typical for cyclical sectors (banks, metals, real estate); betas below 1.0 are expected for defensive sectors (FMCG, pharma).
- Jensen's alpha measures annualized outperformance versus the CAPM prediction. Sectors with negative Jensen alpha underperformed what their beta-implied risk loading would predict — a signal of structural drag beyond market exposure. This does not imply a trading signal; it is a diagnostic characterization of historical risk-adjusted returns.
- All three measures are backward-looking and reflect the full 2006–2026 sample, which spans multiple economic cycles, regulatory changes, and structural breaks. Regime-conditional analysis (see Notebook 04 — HMM Regime Detection) provides a more nuanced read.