# Notebook 08 — Growth & the Transformation Ladder

> Run in: **Local Python environment (PYTHONPATH=. from repo root)**
> Data source: Bloomberg Terminal, FRTL, IIM Calcutta — v2 parquet cache
> Output artifacts: `notebooks/figures/08/*.png`

---


# Notebook 08 — Growth & the Transformation Ladder

**SAAPM Week 1 — Price Levels, Growth Indices, and Stationarity Transforms**

This notebook is part of the Drishti findings series for the Financial Risk Management course at IIM Calcutta (PGDBA Sem 3). It examines long-run growth patterns in Indian equity indices, sector benchmarks, and global commodity futures using Bloomberg Terminal data pulled at FRTL, IIM Calcutta.

**Scope:** Growth-of-₹100 rebasing across 28 series (4 index headlines + 13 sectors + 11 commodities), followed by a formal transformation ladder for the NIFTY Index — illustrating why stationarity transforms are required before time-series modelling.

**Data source:** Bloomberg Terminal, FRTL, IIM Calcutta. For academic/diagnostic use only. This notebook does not constitute investment advice.

**Reference:** SAAPM Week 1 lecture materials; Tsay (2010) *Analysis of Financial Time Series*, Ch. 1–2.

---


```python
import os, sys
sys.path.insert(0, os.path.abspath("."))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme(style="whitegrid")

from pathlib import Path
FIG = Path("notebooks/figures/08")
FIG.mkdir(parents=True, exist_ok=True)

from src.research.series_io import load_index_prices, load_commodity_prices

INDEX_HEADLINES = [
    "NIFTY Index",
    "NSE100 Index",
    "NSEMD150 Index",
    "NSE500 Index",
]

SECTORS = [
    "NSEBANK Index",
    "NSEAUTO Index",
    "NSEFMCG Index",
    "NSEIT Index",
    "NSEMET Index",
    "NSENRG Index",
    "NSEPHRM Index",
    "NSEFIN Index",
    "NSEREALTY Index",
    "NSEPSBK Index",
    "NSEINFR Index",
    "NSEMED Index",
    "NSECON Index",
]

COMMODITIES = [
    "CO1 Comdty",
    "CL1 Comdty",
    "GC1 Comdty",
    "SI1 Comdty",
    "HG1 Comdty",
    "NG1 Comdty",
    "IOE1 Comdty",
    "S 1 Comdty",
    "W 1 Comdty",
    "SB1 Comdty",
    "CT1 Comdty",
]

# Rebase each series to 100 at its own first valid observation.
# Naive px/px.iloc[0] fails when younger series have NaN in row 0.
def rebase(px: pd.DataFrame) -> pd.DataFrame:
    return px.div(px.apply(lambda s: s.loc[s.first_valid_index()])) * 100

print("Preamble loaded. FIG dir:", FIG.resolve())
```

---


## Why we transform price series

A raw equity index level (e.g., NIFTY at 24,000) is a non-stationary process: its mean and variance change over time. Three transformations progressively tame this:

| Step | Transform | What it fixes |
|------|-----------|---------------|
| 1. Raw price | $P_t$ | Trend (upward drift), heteroskedasticity (variance grows with level) |
| 2. Log price | $\ln P_t$ | Linearises exponential growth; variance more stable |
| 3. Log-return | $r_t = \ln P_t - \ln P_{t-1}$ | Removes trend → (approximately) stationary; additive across horizons |

Most risk models (VaR, GARCH, HMM) require stationary inputs. The ADF test (Notebook 09) will formally confirm that raw prices fail and log-returns pass stationarity. This notebook builds the visual intuition first.

---


```python
# ── Index headlines: growth of ₹100 ─────────────────────────────────────────
px_idx = load_index_prices(INDEX_HEADLINES)
rb_idx = rebase(px_idx)

LABEL_MAP = {
    "NIFTY Index":   "NIFTY 50",
    "NSE100 Index":  "NSE 100",
    "NSEMD150 Index":"NSE Midcap 150",
    "NSE500 Index":  "NSE 500",
}
COLORS_IDX = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

fig, ax = plt.subplots(figsize=(12, 5))
for col, color in zip(rb_idx.columns, COLORS_IDX):
    s = rb_idx[col].dropna()
    ax.plot(s.index, s.values, label=LABEL_MAP.get(col, col), color=color, linewidth=1.4)

ax.set_title("Index Headlines — Growth of ₹100", fontsize=14, fontweight="bold")
ax.set_ylabel("Rebased to 100 at first valid date")
ax.set_xlabel("")
ax.legend(loc="upper left", fontsize=10)
ax.set_yscale("log")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:,.0f}"))
fig.tight_layout()
fig.savefig(FIG / "growth_headlines.png", dpi=120)
plt.close(fig)
print("Saved growth_headlines.png")
print(rb_idx.describe().loc[["min","max"]].round(1))
```

---


```python
# ── Sector indices: growth of ₹100 ──────────────────────────────────────────
px_sec = load_index_prices(SECTORS)
rb_sec = rebase(px_sec)

SHORT = {
    "NSEBANK Index":   "Bank",
    "NSEAUTO Index":   "Auto",
    "NSEFMCG Index":   "FMCG",
    "NSEIT Index":     "IT",
    "NSEMET Index":    "Metal",
    "NSENRG Index":    "Energy",
    "NSEPHRM Index":   "Pharma",
    "NSEFIN Index":    "Fin Svcs",
    "NSEREALTY Index": "Realty",
    "NSEPSBK Index":   "PSU Bank",
    "NSEINFR Index":   "Infra",
    "NSEMED Index":    "Media",
    "NSECON Index":    "Consumption",
}

palette = sns.color_palette("tab20", n_colors=len(SECTORS))

fig, ax = plt.subplots(figsize=(14, 6))
for col, color in zip(rb_sec.columns, palette):
    s = rb_sec[col].dropna()
    ax.plot(s.index, s.values, label=SHORT.get(col, col), color=color, linewidth=1.2)

ax.set_title("NSE Sector Indices — Growth of ₹100", fontsize=14, fontweight="bold")
ax.set_ylabel("Rebased to 100 at first valid date")
ax.set_xlabel("")
ax.legend(loc="upper left", fontsize=8, ncol=2)
ax.set_yscale("log")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:,.0f}"))
fig.tight_layout()
fig.savefig(FIG / "growth_sectors.png", dpi=120)
plt.close(fig)
print("Saved growth_sectors.png")
print(rb_sec.describe().loc[["min","max"]].round(1))
```

---


```python
# ── Commodity futures: growth of ₹100 ────────────────────────────────────────
px_com = load_commodity_prices(COMMODITIES)
rb_com = rebase(px_com)

SHORT_COM = {
    "CO1 Comdty":  "Brent Crude",
    "CL1 Comdty":  "WTI Crude",
    "GC1 Comdty":  "Gold",
    "SI1 Comdty":  "Silver",
    "HG1 Comdty":  "Copper",
    "NG1 Comdty":  "Natural Gas",
    "IOE1 Comdty": "Iron Ore",
    "S 1 Comdty":  "Soybeans",
    "W 1 Comdty":  "Wheat",
    "SB1 Comdty":  "Sugar",
    "CT1 Comdty":  "Cotton",
}

palette_com = sns.color_palette("tab20b", n_colors=len(COMMODITIES))

fig, ax = plt.subplots(figsize=(14, 6))
for col, color in zip(rb_com.columns, palette_com):
    s = rb_com[col].dropna()
    ax.plot(s.index, s.values, label=SHORT_COM.get(col, col), color=color, linewidth=1.2)

ax.set_title("Global Commodity Futures — Growth of 100 (base = first valid date)", fontsize=14, fontweight="bold")
ax.set_ylabel("Rebased to 100")
ax.set_xlabel("")
ax.legend(loc="upper left", fontsize=8, ncol=2)
ax.set_yscale("log")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:,.0f}"))
fig.tight_layout()
fig.savefig(FIG / "growth_commodities.png", dpi=120)
plt.close(fig)
print("Saved growth_commodities.png")
print(rb_com.describe().loc[["min","max"]].round(1))
```

---


## The Transformation Ladder

The four panels in Cell 8 step through the canonical stationarity transformation:

1. **Raw price** — shows the long-run trend but is clearly non-stationary: the mean rises, the variance expands with the level. Models like OLS and most time-series tests assume stationarity; using raw prices here leads to spurious regressions.

2. **Simple return** ($r_t = P_t/P_{t-1} - 1$) — removes most of the trend. However, variance is still time-varying (volatility clustering is visible). Convenient for portfolio arithmetic but not additive across time.

3. **Log price** ($\ln P_t$) — linearises exponential growth. The slope of the log series is the continuously compounded return. Still non-stationary in level, but the variance is more homogeneous than the raw price.

4. **Log-return** ($\Delta \ln P_t = \ln P_t - \ln P_{t-1}$) — the working series for all downstream models (GARCH, HMM, DCC, VaR). Approximately stationary, additive across horizons, and easier to model tail risk in. The ADF test in Notebook 09 will formally confirm stationarity for this series.

---


```python
# ── NIFTY transformation ladder ───────────────────────────────────────────────
s_raw = load_index_prices(["NIFTY Index"])["NIFTY Index"].dropna()

fig, axes = plt.subplots(2, 2, figsize=(14, 8))
fig.suptitle("NIFTY Index — Transformation Ladder", fontsize=15, fontweight="bold")

# (a) Raw price
ax = axes[0, 0]
ax.plot(s_raw.index, s_raw.values, color="#1f77b4", linewidth=1.0)
ax.set_title("(a) Raw Price Level  $P_t$")
ax.set_ylabel("Index level")
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:,.0f}"))

# (b) Simple return
s_ret = s_raw.pct_change().dropna()
ax = axes[0, 1]
ax.plot(s_ret.index, s_ret.values * 100, color="#ff7f0e", linewidth=0.7, alpha=0.85)
ax.set_title("(b) Simple Return  $r_t = P_t/P_{t-1}-1$  (%)")
ax.set_ylabel("Daily return (%)")
ax.axhline(0, color="black", linewidth=0.6, linestyle="--")

# (c) Log price
s_log = np.log(s_raw)
ax = axes[1, 0]
ax.plot(s_log.index, s_log.values, color="#2ca02c", linewidth=1.0)
ax.set_title("(c) Log Price  $\\ln P_t$")
ax.set_ylabel("Log index level")

# (d) Log-return (differenced log)
s_logret = s_log.diff().dropna()
ax = axes[1, 1]
ax.plot(s_logret.index, s_logret.values * 100, color="#d62728", linewidth=0.7, alpha=0.85)
ax.set_title("(d) Log-Return  $\\Delta \\ln P_t$  (%)")
ax.set_ylabel("Log-return (%)")
ax.axhline(0, color="black", linewidth=0.6, linestyle="--")

fig.tight_layout()
fig.savefig(FIG / "ladder_nifty.png", dpi=120)
plt.close(fig)
print("Saved ladder_nifty.png")
```

---


```python
# ── NIFTY drawdown underwater chart ──────────────────────────────────────────
s = load_index_prices(["NIFTY Index"])["NIFTY Index"].dropna()
running_max = s.cummax()
drawdown = s / running_max - 1  # always <= 0

fig, ax = plt.subplots(figsize=(14, 4))
ax.fill_between(drawdown.index, drawdown.values * 100, 0,
                color="#d62728", alpha=0.55, label="Drawdown from peak")
ax.plot(drawdown.index, drawdown.values * 100, color="#d62728", linewidth=0.6)
ax.set_title("NIFTY Index — Underwater (Drawdown from Rolling Peak)", fontsize=13, fontweight="bold")
ax.set_ylabel("Drawdown (%)")
ax.set_xlabel("")
ax.axhline(0, color="black", linewidth=0.6)

# Annotate the worst trough
trough_date = drawdown.idxmin()
trough_val = drawdown.min() * 100
ax.annotate(
    f"Deepest: {trough_val:.1f}%\n({trough_date.strftime('%b %Y')})",
    xy=(trough_date, trough_val),
    xytext=(trough_date, trough_val - 5),
    fontsize=9,
    color="#8B0000",
    ha="center",
)

fig.tight_layout()
fig.savefig(FIG / "drawdown_nifty.png", dpi=120)
plt.close(fig)
print("Saved drawdown_nifty.png")
print(f"Peak drawdown: {trough_val:.2f}% on {trough_date.date()}")
print(f"Current drawdown: {drawdown.iloc[-1]*100:.2f}%")
```

---


## Findings

- **Compounding divergence across categories:** Among equity index headlines, the NSE 500 and NSE Midcap 150 have compounded significantly more than the NIFTY 50 over the full history (base ~2000), consistent with the small-cap premium. Sector-level dispersion is wider still — IT and Pharma have been multi-baggers relative to PSU Banks and Media.

- **Commodity growth is cyclical, not compounding:** Most commodity futures (crude oil, natural gas, agricultural) show no sustained upward drift — price levels oscillate around a long-run mean. Gold and copper are partial exceptions with modest real appreciation, reflecting their dual role as store-of-value and industrial demand proxy. This motivates treating commodities as *factor signals* (mean-reverting) rather than *buy-and-hold assets*.

- **Non-stationarity is evident in raw prices:** The transformation ladder confirms the textbook diagnosis: raw NIFTY levels trend upward with expanding variance (heteroskedastic). Log prices linearise the growth path but remain non-stationary in level. Only log-returns satisfy the approximate stationarity required by GARCH, HMM, and VaR models.

- **Volatility clustering is visible in log-returns:** The log-return panel shows clear regime-like bursts of high volatility (2008 GFC, 2020 COVID, 2022 rate-shock episodes) followed by calmer periods. This motivates GARCH modelling (Notebook 06) and HMM regime detection (Notebook 04).

- **Drawdown episodes are deep and prolonged:** The underwater chart shows the NIFTY has experienced peak-to-trough declines of over 50% (GFC 2008) and recoveries taking 3–5 years. This is the key diagnostic for tail-risk management: VaR alone understates loss given the length and severity of historical drawdowns.
