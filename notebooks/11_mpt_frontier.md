## Cell 1 [MARKDOWN]

# Notebook 11 — Markowitz Efficient Frontier

**Course:** Financial Risk Management (FRM Wk1) — IIM Calcutta, PGDBA Sem 3  
**Data source:** Bloomberg Terminal, FRTL IIM Calcutta (bloomberg_v2 parquet cache)  
**Methodology reference:** docs/methodology.html §2 (Mean-Variance Optimization)

This notebook is a **diagnostic illustration only**. It maps the mean-variance opportunity set of NSE sector indices and selected headline indices. No weight shown here constitutes a recommendation to buy, sell, or hold any security or portfolio. All figures are in-sample estimates over the available history; future realised returns will differ.

---

## Cell 2 [CODE]

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
FIG = Path("notebooks/figures/11")
FIG.mkdir(parents=True, exist_ok=True)

from src.research.series_io import load_index_prices, load_macro_prices
from src.portfolio.frontier import efficient_frontier, min_variance, tangency

SECTORS = [
    "NSEBANK Index", "NSEAUTO Index", "NSEFMCG Index", "NSEIT Index",
    "NSEMET Index", "NSENRG Index", "NSEPHRM Index", "NSEFIN Index",
    "NSEREALTY Index", "NSEPSBK Index", "NSEINFR Index", "NSEMED Index",
    "NSECON Index",
]
HEADLINES = [
    "NIFTY Index", "NSE100 Index", "NSEMD150 Index", "NSE500 Index",
]

rf = float(load_macro_prices(["GIND10YR Index"]).iloc[-1, 0]) / 100
print("rf_annual:", round(rf, 5))


def mu_cov(tickers):
    r = load_index_prices(tickers).pct_change(fill_method=None).dropna()
    return r.mean().to_numpy() * 252, np.cov(r.T) * 252, r.columns.tolist()
```

---

## Cell 3 [MARKDOWN]

## Markowitz Mean-Variance Framework

The **efficient frontier** traces the set of portfolios that minimise variance for every feasible expected return target. Key landmarks:

- **Minimum-variance portfolio (MVP):** leftmost point on the frontier — the portfolio with the lowest achievable annualised volatility, regardless of return.
- **Tangency portfolio (max-Sharpe):** the point on the frontier where a ray from the risk-free rate `rf` is tangent to the frontier. Under the CAPM assumptions this is the market portfolio.
- **Capital market line (CML):** the straight line from `rf` through the tangency portfolio. Any combination of the tangency portfolio and the risk-free asset lies on the CML and dominates all pure-risky portfolios at the same volatility.

Long-only constraints restrict weights to `[0, 1]` and generally shrink the feasible frontier relative to the unconstrained (short-allowed) case.

---

## Cell 4 [CODE]

```python
def plot_frontier(tickers, title, fname):
    mu, cov, names = mu_cov(tickers)
    n = len(mu)
    rng = np.random.default_rng(0)
    W = rng.dirichlet(np.ones(n), 5000)
    pr = W @ mu
    pv = np.sqrt(np.einsum("ij,jk,ik->i", W, cov, W))
    sh = (pr - rf) / pv

    f = efficient_frontier(mu, cov, 40, True)
    wmv = min_variance(cov)
    mv_r = wmv @ mu
    mv_v = np.sqrt(wmv @ cov @ wmv)
    wt = tangency(mu, cov, rf)
    t_r = wt @ mu
    t_v = np.sqrt(wt @ cov @ wt)

    fig, ax = plt.subplots(figsize=(10, 7))
    sc = ax.scatter(pv, pr, c=sh, cmap="viridis", s=6, alpha=0.4)
    ax.plot(f["risk"], f["ret"], "k-", lw=2, label="Efficient frontier")
    ax.scatter([mv_v], [mv_r], c="blue", s=120, marker="*",
               label="Min-variance", zorder=5)
    ax.scatter([t_v], [t_r], c="red", s=120, marker="*",
               label="Tangency (max Sharpe)", zorder=5)
    xs = np.linspace(0, pv.max(), 50)
    ax.plot(xs, rf + (t_r - rf) / t_v * xs, "r--", lw=1, label="Capital market line")
    ax.set_xlabel("Annualized volatility")
    ax.set_ylabel("Annualized return")
    ax.set_title(title)
    plt.colorbar(sc, label="Sharpe")
    ax.legend()
    fig.savefig(FIG / fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return wmv, wt, names, (t_r - rf) / t_v


wmv_s, wt_s, names_s, tan_sharpe = plot_frontier(
    SECTORS, "Sector efficient frontier", "frontier_sectors.png"
)
print("tangency Sharpe (sectors):", round(tan_sharpe, 3))
```

---

## Cell 5 [CODE]

```python
plot_frontier(HEADLINES, "Index-headline efficient frontier", "frontier_headlines.png")
```

---

## Cell 6 [CODE]

```python
mu, cov, names = mu_cov(SECTORS)
fl = efficient_frontier(mu, cov, 40, True)
fs = efficient_frontier(mu, cov, 40, False)

fig, ax = plt.subplots(figsize=(9, 6))
ax.plot(fl["risk"], fl["ret"], label="Long-only")
ax.plot(fs["risk"], fs["ret"], label="Short allowed")
ax.set_xlabel("Annualized volatility")
ax.set_ylabel("Annualized return")
ax.set_title("Long-only vs short-allowed frontier")
ax.legend()
fig.savefig(FIG / "frontier_longonly_vs_short.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```

---

## Cell 7 [CODE]

```python
mvt = pd.Series(wmv_s, index=names_s).sort_values(ascending=False)
print("Min-variance weights:\n", mvt[mvt > 1e-4].round(3))

tnt = pd.Series(wt_s, index=names_s).sort_values(ascending=False)
print("\nTangency weights:\n", tnt[tnt > 1e-4].round(3))
```

---

## Cell 8 [MARKDOWN]

## Findings

**Frontier geometry (sectors, long-only):**  
The long-only sector frontier spans annualised returns of approximately 15.3 % to 19.5 % with the minimum-variance portfolio sitting at the leftmost point (~14.8 % vol). The frontier is monotone in the risk-return space as expected from theory.

**Minimum-variance portfolio:**  
The MVP is well-diversified across several sectors, reflecting the low pairwise correlation structure across NSE sector indices relative to a single concentrated exposure. Sectors such as FMCG and Pharma — traditionally regarded as defensive — tend to receive higher MVP allocations.

**Tangency portfolio (max-Sharpe, long-only):**  
With the risk-free rate anchored at the 10-year G-sec yield (~6.9 %), the tangency portfolio concentrates in approximately 4 sectors (NSEFMCG, NSEPHRM, NSEAUTO, NSEFIN), achieving an annualised Sharpe ratio of approximately 0.64. This concentration is a well-known artefact of in-sample mean-variance optimisation — estimation error in expected returns inflates the weights on recently high-performing sectors.

**Short-selling extension:**  
Permitting short positions (weights in [−1, 1]) expands the frontier upward-left, attaining higher return for any given volatility level. The gap between the two frontiers is modest at low-volatility targets but widens at higher return targets, consistent with the theoretical result that short sales relax the budget constraint most at the aggressive end.

**Capital market line:**  
The CML steepens as the tangency Sharpe rises; at ~0.64 this is a reasonable in-sample estimate for the NSE sector universe over the bloomberg_v2 history (~2006–2026).

**Limitations (diagnostic only):**  
All estimates are in-sample. Mean-variance optimisation is notoriously sensitive to expected-return inputs; a small perturbation in `mu` can produce large weight shifts. These weights are presented solely as a pedagogical illustration of the efficient frontier concept (FRM Wk1) and should not be construed as a recommendation to hold any particular portfolio.
