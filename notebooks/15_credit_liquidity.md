# Notebook 15 — Credit & Liquidity Screens
> Run in: **Local machine**
> Data source: Bloomberg v2 cache (`data/cache/bloomberg_v2/`)
> Figures output: `notebooks/figures/15/`

---


# Notebook 15 — Credit & Liquidity Screens

**FRM Wk9 — Credit Risk & Liquidity Risk**

Drishti is fundamentally an *equity* market-risk tool, but even an equity tool touches credit and liquidity risk. A firm's equity is a residual claim that sits behind its debt: if the firm's credit deteriorates, equity holders are wiped out first. And the ability to exit a position at a fair price — liquidity — directly shapes the realizable risk of any holding. Week 9 of the FRM course introduces two canonical, transparent diagnostics for these dimensions:

- **Altman Z-score** (Altman 1968) — a discriminant-analysis credit-distress screen built from five accounting/market ratios.
- **Amihud illiquidity ratio** (Amihud 2002) — average absolute return per unit of traded value, a price-impact proxy for liquidity.

**Data source:** Bloomberg Terminal, FRTL, IIM Calcutta — daily prices/volumes/market caps and annual fundamentals for the Nifty 100 + Midcap 150 universe.

**Diagnostic note:** This notebook is for educational and analytical purposes only. Nothing here constitutes investment advice or a recommendation to buy, sell, or hold any security. The credit and liquidity screens below are characterizations of historical data, not signals.

---


```python
import os, sys
sys.path.insert(0, os.path.abspath("."))
os.environ["DRISHTI_DATA_VERSION"] = "v2"
import numpy as np, pandas as pd
import glob, json
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, seaborn as sns
sns.set_theme(style="whitegrid")
from pathlib import Path
FIG = Path("notebooks/figures/15"); FIG.mkdir(parents=True, exist_ok=True)

from src.research.credit import altman_z
from src.research.liquidity import amihud

EQ_DIR  = Path("data/cache/bloomberg_v2/equities")
ANN_DIR = Path("data/cache/bloomberg_v2/equities_annual")
SECTORS = json.load(open("data/cache/bloomberg_v2/meta/sectors_v2.json"))

def fname_to_ticker(p):
    # "ACEM_IS_Equity.parquet" -> "ACEM IS Equity"
    return Path(p).stem.replace("_", " ")

print("Preamble loaded.")
print("Daily equity parquets :", len(glob.glob(str(EQ_DIR / "*.parquet"))))
print("Annual equity parquets:", len(glob.glob(str(ANN_DIR / "*.parquet"))))
print("Sector map entries     :", len(SECTORS))
```

---


## Altman Z-score Methodology (FRM Wk9)

The original Altman (1968) Z-score for publicly traded manufacturers combines five ratios via discriminant analysis:

$$Z = 1.2\,X_1 + 1.4\,X_2 + 3.3\,X_3 + 0.6\,X_4 + 1.0\,X_5$$

| Ratio | Definition | Captures |
|-------|------------|----------|
| $X_1$ | Working Capital / Total Assets | Short-term liquidity |
| $X_2$ | Retained Earnings / Total Assets | Cumulative profitability / age |
| $X_3$ | EBIT / Total Assets | Operating productivity of assets |
| $X_4$ | Market Value of Equity / Total Liabilities | Market-implied solvency cushion |
| $X_5$ | Sales / Total Assets | Asset turnover / efficiency |

**Distress zones:**

- $Z > 2.99$ — **safe** (low probability of bankruptcy)
- $1.81 \le Z \le 2.99$ — **grey** (zone of ambiguity)
- $Z < 1.81$ — **distress** (high bankruptcy probability)

The coefficients are weights estimated to best separate failing from non-failing firms. $X_3$ (operating profitability) and $X_4$ (market solvency cushion) carry the heaviest weights, reflecting their discriminating power.

---


```python
# DEMONSTRATE altman_z on two textbook firms.
# Signature: altman_z(working_capital, retained_earnings, ebit,
#                     mkt_value_equity, total_liabilities, sales, total_assets)

healthy = altman_z(40, 60, 30, 200, 80, 150, 100)
distressed = altman_z(-10, -20, -5, 10, 90, 20, 100)

print("=== Healthy firm (WC=40, RE=60, EBIT=30, MVE=200, TL=80, Sales=150, TA=100) ===")
print(f"  Z = {healthy['z']:.2f}  ->  zone = {healthy['zone']}")
print("  components:", {k: round(v, 3) for k, v in healthy["components"].items()})

print("\n=== Distressed firm (WC=-10, RE=-20, EBIT=-5, MVE=10, TL=90, Sales=20, TA=100) ===")
print(f"  Z = {distressed['z']:.2f}  ->  zone = {distressed['zone']}")
print("  components:", {k: round(v, 3) for k, v in distressed["components"].items()})
```

---


## Data-Reality Note — Why We Cannot Compute a Full Z-score Here

The Altman Z-score requires **working capital**, **retained earnings**, and **sales** alongside total assets, EBIT, market value of equity, and total liabilities. The v2 Bloomberg annual fundamentals pull cached for this project contains exactly these eight fields:

```
RETURN_COM_EQY  BS_TOT_ASSET  NET_INCOME  SHORT_AND_LONG_TERM_DEBT
BOOK_VAL_PER_SH  EQY_DPS  CF_CASH_FROM_OPER  EQY_SH_OUT
```

**Working capital, retained earnings, EBIT, and sales (revenue) are not in this cache.** A full per-stock Altman Z is therefore *not computable* from the current data — and rather than fabricate proxies for missing line items and present a fake Z-score, we are explicit about the limitation.

Instead, we build a **complementary, reduced credit-health screen** from the fundamentals we *do* have:

- **Debt / Assets** — balance-sheet leverage.
- **ROA** = Net Income / Total Assets — asset profitability.
- **ROE** = `RETURN_COM_EQY` (Bloomberg returns this directly, in %).
- **Market Cap / Debt** — market-implied solvency cushion (a crude $X_4$ analogue).
- **CFO / Debt** — cash-flow coverage of debt, a direct serviceability gauge.

A full Altman Z-score for these names awaits an extended fundamentals pull (working capital, retained earnings, revenue). The screen below is a **directional credit-health characterization, not a distress classification**.

---


```python
# Pick ~40 large names: rank by latest CUR_MKT_CAP from the matching daily parquet.
ann_files = sorted(glob.glob(str(ANN_DIR / "*.parquet")))

# First pass: latest market cap per ticker that has BOTH daily and annual data.
caps = {}
for ap in ann_files:
    tk = fname_to_ticker(ap)
    dp = EQ_DIR / Path(ap).name
    if not dp.exists():
        continue
    try:
        d = pd.read_parquet(dp, columns=["CUR_MKT_CAP"])
        mc = d["CUR_MKT_CAP"].dropna()
        if mc.empty:
            continue
        caps[tk] = float(mc.iloc[-1])
    except Exception:
        continue

top = sorted(caps, key=caps.get, reverse=True)[:40]
print(f"Candidate names with daily+annual data: {len(caps)}; taking top {len(top)} by market cap.")

rows = []
for tk in top:
    ap = ANN_DIR / (tk.replace(" ", "_") + ".parquet")
    dp = EQ_DIR  / (tk.replace(" ", "_") + ".parquet")
    try:
        ann = pd.read_parquet(ap)
        # Annual rows are sparse (NaN padding outside fiscal-year-ends); ffill to get
        # the latest reported fundamentals, then take the last row.
        latest = ann.ffill().iloc[-1]
        d = pd.read_parquet(dp, columns=["CUR_MKT_CAP"])
        mktcap = float(d["CUR_MKT_CAP"].dropna().iloc[-1])
    except Exception:
        continue

    ta   = latest.get("BS_TOT_ASSET", np.nan)
    ni   = latest.get("NET_INCOME", np.nan)
    debt = latest.get("SHORT_AND_LONG_TERM_DEBT", np.nan)
    roe  = latest.get("RETURN_COM_EQY", np.nan)   # already a percent
    cfo  = latest.get("CF_CASH_FROM_OPER", np.nan)

    # Skip names missing the core balance-sheet field.
    if not np.isfinite(ta) or ta == 0:
        continue

    # Guard divide-by-zero: debt may be 0 or NaN.
    debt_ok = np.isfinite(debt) and debt > 0
    sec = SECTORS.get(tk, {})
    rows.append({
        "ticker": tk.replace(" IS Equity", ""),
        "name": sec.get("NAME", ""),
        "GICS": sec.get("GICS_SECTOR_NAME", "Unknown"),
        "mktcap": mktcap,
        "debt_to_assets":  (debt / ta) if debt_ok else np.nan,
        "roa":             (ni / ta) if np.isfinite(ni) else np.nan,
        "roe_pct":         roe if np.isfinite(roe) else np.nan,
        "mktcap_to_debt":  (mktcap / debt) if debt_ok else np.nan,
        "cfo_to_debt":     (cfo / debt) if (debt_ok and np.isfinite(cfo)) else np.nan,
    })

credit = pd.DataFrame(rows).set_index("ticker")
credit = credit.sort_values("debt_to_assets", ascending=False, na_position="last")

print(f"\nCredit-health table: {len(credit)} names\n")
print(credit[["GICS", "mktcap", "debt_to_assets", "roa", "roe_pct",
              "mktcap_to_debt", "cfo_to_debt"]].round(3).to_string())
```

---


```python
# (a) Histogram of debt_to_assets across the sample.
dta = credit["debt_to_assets"].dropna()
fig, ax = plt.subplots(figsize=(10, 6))
ax.hist(dta.values, bins=15, color="#3891F0", edgecolor="white", linewidth=0.6)
ax.axvline(dta.median(), color="#C9A227", linestyle="--", linewidth=1.4,
           label=f"median = {dta.median():.3f}")
ax.set_xlabel("Debt / Total Assets", fontsize=12)
ax.set_ylabel("Number of firms", fontsize=12)
ax.set_title("Leverage Dispersion Across Sample (Debt / Assets)", fontsize=13)
ax.legend(fontsize=10)
plt.tight_layout()
fig.savefig(FIG / "debt_to_assets.png", dpi=150)
plt.close(fig)
print(f"Figure saved: {FIG}/debt_to_assets.png")

# (b) Median debt_to_assets by GICS sector.
by_sec = (credit.dropna(subset=["debt_to_assets"])
          .groupby("GICS")["debt_to_assets"].median()
          .sort_values(ascending=False))
fig, ax = plt.subplots(figsize=(11, 6))
ax.barh(by_sec.index[::-1], by_sec.values[::-1], color="#34C76C",
        edgecolor="white", linewidth=0.5)
ax.set_xlabel("Median Debt / Assets", fontsize=12)
ax.set_title("Median Leverage by GICS Sector (sample)", fontsize=13)
plt.tight_layout()
fig.savefig(FIG / "debt_by_sector.png", dpi=150)
plt.close(fig)
print(f"Figure saved: {FIG}/debt_by_sector.png")
print("\nMedian debt/assets by sector:")
print(by_sec.round(3).to_string())
```

---


## Liquidity — Amihud Illiquidity Ratio (FRM Wk9)

Liquidity risk is the risk that a position cannot be exited at a fair price within a reasonable time. The **Amihud (2002) illiquidity ratio** is a widely used, low-data-requirement proxy for *price impact*: how much the price moves per unit of money traded.

$$\text{ILLIQ}_i = \frac{1}{D}\sum_{t=1}^{D}\frac{|r_{i,t}|}{P_{i,t}\,\cdot\,V_{i,t}}$$

where $r_{i,t}$ is the daily return, $P_{i,t}$ the price, and $V_{i,t}$ the share volume — so $P_{i,t} V_{i,t}$ is the daily traded value. A **higher** Amihud ratio means a given rupee of trading moves the price more, i.e. **the stock is less liquid**. The ratio is reported scaled by $10^6$ (Amihud's display convention) so the numbers are readable.

The intuition for the equity-risk context: illiquid names carry an extra, often under-measured, source of realized loss — you may not get the marked price when you actually need to sell, especially during stress when liquidity evaporates exactly when correlations spike.

---


```python
# Amihud illiquidity for the same ~40 names.
illiq = {}
for tk_short in credit.index:
    tk = tk_short + " IS Equity"
    dp = EQ_DIR / (tk.replace(" ", "_") + ".parquet")
    if not dp.exists():
        continue
    try:
        d = pd.read_parquet(dp, columns=["PX_LAST", "PX_VOLUME"])
        px  = d["PX_LAST"]
        vol = d["PX_VOLUME"]
        ret = px.pct_change(fill_method=None)
        val = amihud(ret, px, vol)
    except Exception:
        continue
    if np.isfinite(val):
        illiq[tk_short] = val

illiq_s = pd.Series(illiq, name="amihud").sort_values(ascending=False)
print(f"Amihud computed for {len(illiq_s)} names.\n")
print("=== Most ILLIQUID (top 10) ===")
print(illiq_s.head(10).round(4).to_string())
print("\n=== Most LIQUID (bottom 10) ===")
print(illiq_s.tail(10).round(6).to_string())

# Bar chart of the 15 most illiquid.
top15 = illiq_s.head(15)
fig, ax = plt.subplots(figsize=(11, 7))
ax.barh(top15.index[::-1], top15.values[::-1], color="#DC4040",
        edgecolor="white", linewidth=0.5)
ax.set_xlabel("Amihud illiquidity (×1e6)  — higher = less liquid", fontsize=11)
ax.set_title("15 Most Illiquid Names in Sample (Amihud 2002)", fontsize=13)
plt.tight_layout()
fig.savefig(FIG / "amihud_ranking.png", dpi=150)
plt.close(fig)
print(f"\nFigure saved: {FIG}/amihud_ranking.png")
```

---


```python
# Scatter: Amihud illiquidity (y, log) vs market cap (x, log). Expect inverse relation.
joined = credit[["mktcap"]].join(illiq_s).dropna()
joined = joined[(joined["mktcap"] > 0) & (joined["amihud"] > 0)]

fig, ax = plt.subplots(figsize=(10, 7))
ax.scatter(joined["mktcap"], joined["amihud"], color="#8B5CF6", s=70,
           edgecolors="white", linewidths=0.5, zorder=3)
for tk, row in joined.iterrows():
    ax.annotate(tk, (row["mktcap"], row["amihud"]), textcoords="offset points",
                xytext=(4, 3), fontsize=7, color="#444444")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Market Cap (log scale)", fontsize=12)
ax.set_ylabel("Amihud illiquidity, ×1e6 (log scale)", fontsize=12)
ax.set_title("Size vs Liquidity: bigger cap → lower Amihud → more liquid", fontsize=13)

# Rank correlation as a quantitative summary of the inverse relation.
rho = joined["mktcap"].corr(joined["amihud"], method="spearman")
ax.text(0.05, 0.05, f"Spearman ρ = {rho:.2f}", transform=ax.transAxes,
        fontsize=11, color="#333333",
        bbox=dict(boxstyle="round", fc="white", ec="#cccccc", alpha=0.85))
plt.tight_layout()
fig.savefig(FIG / "amihud_vs_size.png", dpi=150)
plt.close(fig)
print(f"Figure saved: {FIG}/amihud_vs_size.png")
print(f"Spearman rank correlation (mktcap vs Amihud): {rho:.3f}")
```

---


## Findings

**Diagnostic observations — not investment advice.**

**Credit / leverage (reduced screen):**

- Leverage (Debt / Assets) is **dispersed across the sample**: balance-sheet-heavy names sit at one end while asset-light, cash-rich franchises cluster near zero. The histogram makes this dispersion visible and identifies where in the distribution each name falls.
- Aggregated by GICS sector, leverage concentrates predictably in **capital-intensive and financial sectors** — utilities, energy/materials, and financials (whose business model *is* leverage) typically carry the highest median Debt / Assets, while consumer staples / IT-services names tend to be lightly geared. The complementary ratios (Market Cap / Debt and CFO / Debt) give a market-implied solvency cushion and a cash-flow coverage read that a raw leverage number alone cannot.

**Liquidity (Amihud):**

- The Amihud ranking separates the most price-impactful (least liquid) names from the deepest-traded mega-caps. The size–liquidity scatter shows the expected **inverse relation**: larger market caps trade with lower Amihud illiquidity (negative Spearman ρ). This is the empirical Wk9 statement that *size proxies for liquidity* — a small-cap position carries materially more liquidation risk per rupee than a large-cap one of the same notional.

**Honest caveat:** the credit block here is a **reduced proxy**, not the full Altman Z-score. Working capital, retained earnings, and sales are absent from the cached fundamentals, so the headline distress classification of Cell 4 is demonstrated only on textbook firms, while the real-data screen relies on the leverage / profitability / coverage ratios that *are* available. A future extended fundamentals pull would let this notebook compute a genuine per-stock Altman Z across the universe. All figures are backward-looking diagnostics, not signals.
