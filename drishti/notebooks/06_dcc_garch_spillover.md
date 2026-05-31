# Notebook 06 — DCC-GARCH + Diebold-Yilmaz Spillover
> Run in: **BQuant (Bloomberg hosted Python environment at FRTL)**
> Inputs: `sector_returns.parquet`, `commodity_returns.parquet`, `macro_series.parquet` (from Notebook 01)
> Output artifacts: `dcc_correlations.parquet`, `spillover_table.json`

---

## Cell 1 [MARKDOWN]

# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti's primary research contribution is measuring how commodity and macro shocks transmit risk into Indian equity sectors — what the literature calls *volatility spillover*. This is motivated directly by the assigned reading (Mukherjee-Bardhan gold spillover paper), which uses a VAR-MGARCH/DCC framework, and is the methodological standard for the Indian equity-commodity spillover literature.

Understanding spillover has a direct risk management application: if Brent crude shocks transmit strongly into the energy and metals sectors, a portfolio concentrated in those sectors has hidden commodity tail risk that does not appear in standard VaR calculations using only equity price history.

---

## Cell 2 [MARKDOWN]

## Notebook 06 — DCC-GARCH + Diebold-Yilmaz Spillover

**What this notebook does:**

Implements two complementary spillover methodologies:

**Method 1: DCC-GARCH (Dynamic Conditional Correlation)**
- Fits GARCH(1,1) to each series to capture time-varying volatility.
- Estimates DCC parameters (α, β) to track how correlations evolve over time.
- Output: time-varying correlation between each (sector, commodity/macro) pair.
- Key finding: correlation spikes during crises — COVID 2020, 2022 drawdown.

**Method 2: Diebold-Yilmaz (2012) Connectedness Index**
- Fits a VAR(p) to all sector + commodity series jointly.
- Computes the generalized FEVD (Pesaran-Shin, order-invariant).
- Output: directional spillover table — who transmits, who receives.
- Key metric: **total connectedness index** = % of forecast-error variance explained by cross-market shocks.

**Together, these answer:**
- *DCC:* "How does the crude-energy correlation change during crises?"
- *DY:* "What fraction of energy sector volatility originates from commodity shocks?"

**Reference:** Diebold & Yilmaz (2012), *Better to Give than to Receive*, IJF.

---

## Cell 3 [CODE]

```python
# ── Imports ────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
from arch import arch_model
from statsmodels.tsa.api import VAR
from scipy.optimize import minimize
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

INPUT_DIR  = Path("/bquant/data/drishti")
OUTPUT_DIR = INPUT_DIR

print("Loading data from Notebook 01 exports...")
```

---

## Cell 4 [CODE]

```python
# ── Load and align data ──────────────────────────────────────────────────────
sector_returns    = pd.read_parquet(INPUT_DIR / "sector_returns.parquet")
commodity_returns = pd.read_parquet(INPUT_DIR / "commodity_returns.parquet")

# For DCC and DY, use sector indices + primary commodity factors
# Limit to 6-8 series for computational tractability
SECTOR_COLS    = ["energy", "metals", "fmcg", "it"]
COMMODITY_COLS = ["brent", "gold", "copper", "usdinr"]

sector_sel    = sector_returns[SECTOR_COLS]
commodity_sel = commodity_returns[COMMODITY_COLS]

combined = pd.concat([sector_sel, commodity_sel], axis=1).dropna()
print(f"Combined matrix: {combined.shape}")
print(f"  Series: {list(combined.columns)}")
print(f"  Date range: {combined.index[0].date()} to {combined.index[-1].date()}")
```

---

## Cell 5 [MARKDOWN]

### DCC-GARCH — Step 1: Univariate GARCH(1,1)

For each series, fit a GARCH(1,1) to model its time-varying conditional volatility. Extract the **standardized residuals** (z_t = r_t / σ_t). These residuals have roughly unit variance but retain the correlation structure — they are the input to the DCC estimation.

GARCH(1,1) model: σ²_t = ω + α·r²_{t-1} + β·σ²_{t-1}

Stationarity requires α + β < 1.

---

## Cell 6 [CODE]

```python
# ── Step 1: Fit GARCH(1,1) to each series ────────────────────────────────────
std_resids = {}   # {series_name: np.ndarray of standardized residuals}
garch_params = {}

for col in combined.columns:
    r_pct = combined[col] * 100   # arch library expects percentage scale

    model = arch_model(r_pct, vol="GARCH", p=1, q=1, dist="normal", rescale=False)
    res   = model.fit(disp="off", show_warning=False)

    omega = res.params["omega"]
    alpha = res.params["alpha[1]"]
    beta  = res.params["beta[1]"]
    persistence = alpha + beta

    std_resids[col] = res.std_resid.dropna().values

    garch_params[col] = {
        "omega": round(float(omega), 6),
        "alpha": round(float(alpha), 4),
        "beta":  round(float(beta),  4),
        "persistence": round(float(persistence), 4),
        "unconditional_vol": round(
            float(np.sqrt(omega / max(1 - persistence, 1e-6))) / 100, 4
        ),
    }

    print(f"  {col:12s}  α={alpha:.3f}  β={beta:.3f}  persistence={persistence:.3f}")
```

---

## Cell 7 [MARKDOWN]

### DCC-GARCH — Step 2: DCC parameter estimation

The DCC model updates the correlation matrix Q_t as:

Q_t = (1 - α_DCC - β_DCC) × Q̄ + α_DCC × (z_{t-1} z'_{t-1}) + β_DCC × Q_{t-1}

where Q̄ is the unconditional covariance of standardized residuals.
The conditional correlation matrix is:
R_t = diag(Q_t)^{-1/2} × Q_t × diag(Q_t)^{-1/2}

Parameters α_DCC and β_DCC are estimated by maximum likelihood.
The constraint α_DCC + β_DCC < 1 ensures stationarity of the DCC process.

---

## Cell 8 [CODE]

```python
# ── Step 2: Estimate DCC parameters ─────────────────────────────────────────

# Stack standardized residuals into matrix (align to minimum length)
min_len = min(len(v) for v in std_resids.values())
col_names = list(combined.columns)
Z = np.column_stack([std_resids[c][-min_len:] for c in col_names])
Q_bar = np.cov(Z.T)   # unconditional correlation of standardized residuals


def dcc_neg_loglik(params: np.ndarray) -> float:
    """Negative log-likelihood for DCC(1,1) parameters."""
    a, b = params
    if a <= 0 or b <= 0 or a + b >= 1:
        return 1e10

    T, k = Z.shape
    Q = Q_bar.copy()
    ll = 0.0

    for t in range(1, T):
        z_prev = Z[t - 1, :]
        Q = (1 - a - b) * Q_bar + a * np.outer(z_prev, z_prev) + b * Q

        # Normalize Q to correlation matrix R
        d_inv = np.diag(1.0 / np.sqrt(np.maximum(np.diag(Q), 1e-10)))
        R     = d_inv @ Q @ d_inv

        z_t = Z[t, :]
        try:
            sign, logdet = np.linalg.slogdet(R)
            if sign <= 0:
                return 1e10
            R_inv = np.linalg.solve(R, np.eye(k))
            # DCC log-likelihood contribution (correlation part only)
            ll += -0.5 * (logdet + z_t @ R_inv @ z_t - z_t @ z_t)
        except np.linalg.LinAlgError:
            return 1e10

    return -ll


# Optimize DCC parameters
opt = minimize(
    dcc_neg_loglik,
    x0=[0.01, 0.95],
    method="L-BFGS-B",
    bounds=[(1e-6, 0.3), (1e-6, 0.99)],
    options={"maxiter": 200, "ftol": 1e-9},
)

dcc_alpha, dcc_beta = opt.x
print(f"DCC parameters: α={dcc_alpha:.4f}, β={dcc_beta:.4f}")
print(f"Persistence: α+β = {dcc_alpha+dcc_beta:.4f}")
```

---

## Cell 9 [MARKDOWN]

### Step 3: Compute time-varying correlations

With DCC parameters estimated, we compute R_t for every t in the sample. The resulting time series of pairwise correlations is the primary output — we focus on sector-commodity pairs (e.g., energy-brent, metals-copper) and examine how they spike during crisis periods.

---

## Cell 10 [CODE]

```python
# ── Step 3: Compute full R_t time series ─────────────────────────────────────
T, k = Z.shape
Q = Q_bar.copy()

# Align dates: std_resids are shorter by initial GARCH burnin
# Use last min_len dates from combined
dates = combined.index[-min_len:]

# Build correlation time series for all pairs
pair_names = [f"{col_names[i]}_{col_names[j]}"
              for i in range(k) for j in range(i+1, k)]
corr_ts = {p: [] for p in pair_names}

for t in range(1, T):
    z = Z[t-1, :]
    Q = (1 - dcc_alpha - dcc_beta) * Q_bar + dcc_alpha * np.outer(z, z) + dcc_beta * Q
    d_inv = np.diag(1.0 / np.sqrt(np.maximum(np.diag(Q), 1e-10)))
    R     = d_inv @ Q @ d_inv

    for i in range(k):
        for j in range(i+1, k):
            corr_ts[f"{col_names[i]}_{col_names[j]}"].append(float(R[i, j]))

# Build DataFrame (dates[1:] since first observation has no lag)
corr_df = pd.DataFrame(corr_ts, index=dates[1:])
print(f"Time-varying correlations: {corr_df.shape}")
print(f"\nRecent average correlations (last 60 days):")
print(corr_df.tail(60).mean().round(3))
```

---

## Cell 11 [CODE]

```python
# ── Crisis correlation analysis ───────────────────────────────────────────────
import matplotlib.pyplot as plt

CRISIS_WINDOWS = {
    "Normal (2021 H2)":   ("2021-06-01", "2021-12-31"),
    "COVID crash 2020":   ("2020-02-01", "2020-04-30"),
    "2022 drawdown":      ("2022-01-01", "2022-06-30"),
}

# Focus on energy-brent and metals-copper as the headline pairs
focus_pairs = ["energy_brent", "metals_copper"]
focus_pairs = [p for p in focus_pairs if p in corr_df.columns]

print("Average DCC correlation by period:")
print(f"{'Period':30s}  " + "  ".join(f"{p:20s}" for p in focus_pairs))
for label, (s, e) in CRISIS_WINDOWS.items():
    sub = corr_df.loc[s:e]
    if sub.empty:
        continue
    vals = "  ".join(f"{sub[p].mean():.3f}" if p in sub.columns else "  N/A " for p in focus_pairs)
    print(f"{label:30s}  {vals}")

# Chart
fig, axes = plt.subplots(len(focus_pairs), 1, figsize=(14, 4 * len(focus_pairs)), sharex=True)
if len(focus_pairs) == 1:
    axes = [axes]

for ax, pair in zip(axes, focus_pairs):
    ax.plot(corr_df.index, corr_df[pair], color="#145c72", linewidth=0.8)
    ax.axhline(0, color="gray", linewidth=0.5)
    # Shade crisis windows
    for label, (s, e) in CRISIS_WINDOWS.items():
        if label != "Normal (2021 H2)":
            ax.axvspan(pd.Timestamp(s), pd.Timestamp(e), alpha=0.15, color="#a33b3b")
    ax.set_title(f"DCC Correlation: {pair.replace('_', ' → ')}", fontsize=10)
    ax.set_ylabel("Conditional Correlation")
    ax.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "dcc_correlations.png", dpi=150, bbox_inches="tight")
plt.show()
print("Chart saved.")
```

---

## Cell 12 [MARKDOWN]

### Diebold-Yilmaz Connectedness Index

**FEVD approach:** We fit a VAR(p) and compute the H-step generalized forecast error variance decomposition using the Pesaran-Shin (1998) generalized IRF approach. Unlike Cholesky decomposition, this is **order-invariant** — results don't change if we reorder the variables.

Entry (i,j) of the DY table = fraction of H-step forecast error variance of variable i attributable to shocks from variable j.

**Total connectedness** = sum of all off-diagonal entries / k = average fraction of variance that comes from *other* series.

---

## Cell 13 [CODE]

```python
# ── Diebold-Yilmaz: Fit VAR ──────────────────────────────────────────────────
from statsmodels.tsa.api import VAR

data = combined.dropna()
k    = len(data.columns)
names = list(data.columns)

# Select VAR lag order via AIC (cap at 5 to avoid overparameterisation)
var_model = VAR(data.values)
lag_order = var_model.select_order(maxlags=5, verbose=False).aic
lag_order = max(1, min(lag_order, 5))

fitted = var_model.fit(lag_order)
print(f"VAR lag order selected (AIC): {lag_order}")
print(f"VAR fitted. Residual std:")
for i, n in enumerate(names):
    print(f"  {n:12s}: {fitted.sigma_u[i,i]**0.5*100:.3f}%")
```

---

## Cell 14 [CODE]

```python
# ── Generalized FEVD (Pesaran-Shin) ─────────────────────────────────────────
FEVD_HORIZON = 10   # 10-day ahead FEVD

sigma    = fitted.sigma_u
coefs    = fitted.coefs       # shape (p, k, k)
p_lags   = len(coefs)

# Moving-average coefficients Ψ_h for h = 0..H-1
Psi = np.zeros((FEVD_HORIZON, k, k))
Psi[0] = np.eye(k)
for h in range(1, FEVD_HORIZON):
    for j in range(min(h, p_lags)):
        Psi[h] += coefs[j] @ Psi[h - 1 - j]

# Generalized FEVD: theta[i,j] = share of i's h-step FEVD from j's shock
sigma_diag = np.diag(sigma)
theta = np.zeros((k, k))

for i in range(k):
    e_i   = np.eye(k)[i]
    denom = sum(float(e_i @ Psi[h] @ sigma @ Psi[h].T @ e_i)
                for h in range(FEVD_HORIZON))
    for j in range(k):
        e_j = np.eye(k)[j]
        numer = sum(float((e_i @ Psi[h] @ sigma @ e_j) ** 2)
                    for h in range(FEVD_HORIZON))
        theta[i, j] = numer / (sigma_diag[j] * denom) if denom > 0 else 0.0

# Row-normalize
row_sums = theta.sum(axis=1, keepdims=True)
theta_norm = theta / np.where(row_sums > 0, row_sums, 1.0)

# Build DY table
dy_df = pd.DataFrame(theta_norm * 100, index=names, columns=names)

# Total connectedness
total_conn = float((theta_norm.sum() - np.trace(theta_norm)) / k * 100)

print(f"\nDiebold-Yilmaz Total Connectedness Index: {total_conn:.1f}%")
print(f"(% of H={FEVD_HORIZON}-step forecast error variance from cross-market shocks)")
print(f"\nSpillover table (row i from column j):")
print(dy_df.round(1).to_string())
```

---

## Cell 15 [CODE]

```python
# ── Directional spillover: To / From / Net ────────────────────────────────────
# "To j" = contribution of j's shocks to other variables' FEVDs
to_spillover   = {names[j]: float((theta_norm[:, j].sum() - theta_norm[j, j]) / k * 100)
                  for j in range(k)}
from_spillover = {names[i]: float((theta_norm[i, :].sum() - theta_norm[i, i]) * 100)
                  for i in range(k)}
net_spillover  = {n: to_spillover[n] - from_spillover[n] for n in names}

summary_df = pd.DataFrame({
    "To (transmitter)":   to_spillover,
    "From (receiver)":    from_spillover,
    "Net":                net_spillover,
}).round(2)

print("\nDirectional Spillover Summary:")
print(summary_df.to_string())
print("\nPositive net = net transmitter of risk (commodity factors typically)")
print("Negative net = net receiver of risk (sector indices typically)")
```

---

## Cell 16 [CODE]

```python
# ── DY heatmap ────────────────────────────────────────────────────────────────
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(9, 7))
im = ax.imshow(dy_df.values, cmap="YlOrRd", aspect="auto", vmin=0)

ax.set_xticks(range(k)); ax.set_yticks(range(k))
ax.set_xticklabels(names, rotation=30, ha="right")
ax.set_yticklabels(names)

for i in range(k):
    for j in range(k):
        val = dy_df.values[i, j]
        color = "white" if val > 15 else "black"
        ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                fontsize=9, color=color)

ax.set_title(f"Diebold-Yilmaz Spillover Table (H={FEVD_HORIZON} days)\n"
             f"Entry [i,j]: % of i's forecast error variance from j's shocks\n"
             f"Total Connectedness: {total_conn:.1f}%",
             fontsize=10)

plt.colorbar(im, ax=ax, label="Spillover (%)")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "dy_spillover_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()
print("Heatmap saved.")
```

---

## Cell 17 [CODE]

```python
# ── Export artifacts ──────────────────────────────────────────────────────────

# 1. DCC time-varying correlations
corr_df.to_parquet(OUTPUT_DIR / "dcc_correlations.parquet")

# 2. Spillover table
spillover_export = {
    "total_connectedness": round(total_conn, 2),
    "var_lag": int(lag_order),
    "fevd_horizon": FEVD_HORIZON,
    "to_spillover":   {k: round(v, 2) for k, v in to_spillover.items()},
    "from_spillover": {k: round(v, 2) for k, v in from_spillover.items()},
    "net_spillover":  {k: round(v, 2) for k, v in net_spillover.items()},
    "pairwise_pct":   dy_df.round(2).to_dict(),
    "dcc_alpha": round(float(dcc_alpha), 4),
    "dcc_beta":  round(float(dcc_beta),  4),
    "garch_params": garch_params,
}

with open(OUTPUT_DIR / "spillover_table.json", "w") as f:
    json.dump(spillover_export, f, indent=2)

print("✅ Exported:")
print(f"  dcc_correlations.parquet  ({len(corr_df)} rows, {len(corr_df.columns)} pairs)")
print(f"  spillover_table.json      (DY total connectedness: {total_conn:.1f}%)")
```
