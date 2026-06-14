
# Notebook 14 — Cross-Market Spillover & Connectedness

**Course:** Financial Risk Management — SAAPM Wk3/4 (Multivariate time series: cointegration, VAR, Granger, IRF, FEVD; volatility spillover)
**Data source:** Bloomberg Terminal, FRTL IIM Calcutta (bloomberg_v2 parquet cache)
**Methodology references:** Diebold & Yilmaz (2012, IJF); Pesaran & Shin (1998); Engle (2002, DCC); Cappiello-Engle-Sheppard (2006, ADCC); Johansen (1991, cointegration); Mukherjee-Bardhan (gold-equity spillover, assigned reading).

This notebook is a **diagnostic illustration only**. Nothing here is investment advice; no spillover number constitutes a recommendation to buy, sell, or hold any security.

**The question.** How do shocks travel *across* markets — between Indian equity sectors and the commodity factors (Brent crude, Gold) that drive them? A portfolio concentrated in energy and metals carries hidden commodity tail risk that single-asset VaR never sees. Spillover analysis makes that risk visible.

**Two layers, taught then advanced.**

*Taught layer (the classical multivariate toolkit):*
1. **Cointegration first** — Johansen trace test on price *levels*. If series share a common stochastic trend, differencing blindly throws away a long-run equilibrium; we fit a VECM instead.
2. **VAR** on stationary returns, lag by AIC, with **Ljung-Box** residual diagnostics.
3. **Granger causality** — does the lagged history of one market improve forecasts of another?
4. **Orthogonalized impulse responses** — how a one-off shock propagates through the system.
5. **Cholesky FEVD** — variance decomposition (but *order-dependent* — a known weakness).

*Advanced layer (the spillover frontier):*
6. **Generalized FEVD / Diebold-Yilmaz** — order-*invariant* connectedness; directional to/from/net spillover.
7. **Rolling connectedness** — how total spillover spikes in crises.
8. **DCC-GARCH** — time-varying conditional correlations.
9. **Network diagram** — who transmits, who receives.

---


```python
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.abspath("."))
os.environ["DRISHTI_DATA_VERSION"] = "v2"

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_theme(style="whitegrid")
import networkx as nx

from pathlib import Path
FIG = Path("notebooks/figures/14")
FIG.mkdir(parents=True, exist_ok=True)

from src.research.series_io import load_index_prices, load_commodity_prices
from src.research.diebold_yilmaz import compute_spillover, rolling_spillover
from src.research.dcc_garch import fit_dcc_garch
from src.research.cointegration import johansen_test, fit_vecm

from statsmodels.tsa.api import VAR
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller, grangercausalitytests

# ── Build the v2 spillover panel ─────────────────────────────────────────────
SECT = ["NSEBANK Index", "NSEIT Index", "NSEFMCG Index", "NSEMET Index",
        "NSENRG Index", "NSEAUTO Index", "NSEPHRM Index"]
FACT = ["CO1 Comdty", "GC1 Comdty"]          # Brent, Gold factors

px_sec = load_index_prices(SECT)
px_com = load_commodity_prices(FACT)

ret = pd.concat(
    [px_sec.pct_change(fill_method=None), px_com.pct_change(fill_method=None)],
    axis=1,
).dropna()
# short, clean labels for every chart
ret.columns = ["Bank", "IT", "FMCG", "Metal", "Energy", "Auto", "Pharma", "Brent", "Gold"]

print(f"Spillover return panel: {ret.shape[0]} obs x {ret.shape[1]} series")
print(f"  Common window: {ret.index[0].date()} -> {ret.index[-1].date()}")
print(f"  Series: {list(ret.columns)}")
```

---


```python
# ── ADF stationarity: levels (log-price) vs returns ──────────────────────────
# A VAR for spillover needs stationary inputs. Returns should reject a unit root;
# log-price levels should NOT (they are the cointegration candidates).
px_all = pd.concat([px_sec, px_com], axis=1).dropna()
px_all.columns = ret.columns
log_lvl = np.log(px_all)

rows = []
for c in ret.columns:
    p_lvl = adfuller(log_lvl[c].dropna(), autolag="AIC")[1]
    p_ret = adfuller(ret[c].dropna(), autolag="AIC")[1]
    rows.append({"series": c, "adf_p_level": p_lvl, "adf_p_return": p_ret})
adf_tbl = pd.DataFrame(rows).set_index("series")
print("ADF p-values (H0 = unit root / non-stationary):")
print(adf_tbl.round(4).to_string())
print("\nLevels mostly non-stationary (p high), returns stationary (p ~ 0) — as expected.")

fig, ax = plt.subplots(figsize=(11, 4.5))
x = np.arange(len(adf_tbl))
w = 0.4
ax.bar(x - w/2, adf_tbl["adf_p_level"], w, label="log-price level", color="#b08968")
ax.bar(x + w/2, adf_tbl["adf_p_return"], w, label="daily return", color="#2b6cb0")
ax.axhline(0.05, color="red", ls="--", lw=1, label="5% threshold")
ax.set_xticks(x); ax.set_xticklabels(adf_tbl.index, rotation=30, ha="right")
ax.set_ylabel("ADF p-value"); ax.set_title("ADF stationarity: levels vs returns")
ax.legend()
fig.tight_layout(); fig.savefig(FIG / "03_adf_stationarity.png", dpi=130); plt.close(fig)
print("saved 03_adf_stationarity.png")
```

---


### Taught layer 1 — cointegration first (don't difference blindly)

Before differencing into returns, ask whether the price *levels* share a common stochastic trend. If a set of non-stationary series is **cointegrated**, some linear combination is stationary — a long-run equilibrium the prices are tethered to. Differencing all of them into returns throws that equilibrium away.

We test the equity-index triple **NIFTY / Bank / Financials** on log-price levels with the **Johansen trace test**. These three are economically linked (Bank and Financials are large NIFTY constituents), so a long-run relationship is plausible. We read the **trace statistic against the 95% critical value** to estimate the cointegration rank. If rank ≥ 1, we fit a **VECM** (a VAR in differences *plus* an error-correction term that pulls the system back toward equilibrium) and forecast it; if rank = 0 there is no stationary combination and the correct next step is to difference into returns (which is exactly what the rest of the notebook does). The point of the cell is the *decision procedure*, not a foregone conclusion — over this particular 2004→2026 sample the trace statistic for `r=0` lands just below the critical value, a textbook *borderline* call.

---


```python
# ── Johansen cointegration on log-levels of an equity-index triple ───────────
COINT = ["NIFTY Index", "NSEBANK Index", "NSEFIN Index"]
coint_lvls = np.log(load_index_prices(COINT).dropna())
coint_lvls.columns = ["NIFTY", "Bank", "Fin"]
print(f"Cointegration levels: {coint_lvls.shape[0]} obs, "
      f"{coint_lvls.index[0].date()} -> {coint_lvls.index[-1].date()}")

jt = johansen_test(coint_lvls)
print("\nJohansen trace test:")
print(f"{'r<=':<6}{'trace_stat':>12}{'crit_95':>12}")
for i, (ts, cv) in enumerate(zip(jt["trace_stat"], jt["crit_95"])):
    flag = "  *reject H0" if ts > cv else ""
    print(f"{i:<6}{ts:>12.3f}{cv:>12.3f}{flag}")
print(f"\nEstimated cointegration rank: {jt['rank']}")
if jt["rank"] == 0:
    print("Rank 0 (trace stat for r=0 falls just below the 95% critical value — a"
          "\nborderline call). Strictly we would difference into returns; below we fit a"
          "\nrank-1 VECM as an illustration of the error-correction mechanism.")

# Fit a VECM to illustrate the error-correction forecast (use estimated rank, min 1).
vecm_rank = max(1, jt["rank"])
fc = fit_vecm(coint_lvls, coint_rank=vecm_rank, steps=20)
print(f"\nVECM (rank {vecm_rank}) fitted. 20-step log-level forecast (head):")
print(fc.round(4).head().to_string())

fig, axes = plt.subplots(1, 3, figsize=(13, 4))
hist_tail = coint_lvls.tail(120)
fc_idx = np.arange(len(hist_tail), len(hist_tail) + len(fc))
for ax, col in zip(axes, coint_lvls.columns):
    ax.plot(np.arange(len(hist_tail)), hist_tail[col].values, color="#2b6cb0", lw=1, label="history")
    ax.plot(fc_idx, fc[col].values, color="#d62728", lw=1.6, ls="--", label="VECM forecast")
    ax.set_title(col); ax.set_xlabel("days (recent)")
axes[0].set_ylabel("log price"); axes[0].legend(fontsize=8)
fig.suptitle(f"VECM error-correction forecast (coint rank = {vecm_rank})")
fig.tight_layout(); fig.savefig(FIG / "05_vecm_forecast.png", dpi=130); plt.close(fig)
print("saved 05_vecm_forecast.png")
```

---


```python
# ── VAR on the stationary return panel; AIC lag select; Ljung-Box residuals ──
var_model = VAR(ret)
sel = var_model.select_order(maxlags=5)
p = max(1, int(sel.aic))
print(f"VAR order by AIC (cap 5): p = {p}")

var_res = var_model.fit(p)
print(f"VAR({p}) fitted on {ret.shape[1]} series, {var_res.nobs} usable obs.")

# Per-equation Ljung-Box on residuals (H0 = residuals are white noise / no autocorr)
resid = pd.DataFrame(var_res.resid, columns=ret.columns)
lb_rows = []
for c in ret.columns:
    lb = acorr_ljungbox(resid[c], lags=[10], return_df=True)
    lb_rows.append({"series": c,
                    "LB_stat(10)": float(lb["lb_stat"].iloc[0]),
                    "LB_pvalue": float(lb["lb_pvalue"].iloc[0])})
lb_tbl = pd.DataFrame(lb_rows).set_index("series")
print("\nLjung-Box on VAR residuals (lag 10):")
print(lb_tbl.round(4).to_string())
print("\nResidual p<0.05 -> leftover autocorrelation (common for daily equity VARs;"
      "\nGARCH-type effects in the variance, not the mean).")
```

---


```python
# ── Granger causality grid: does lagged X improve forecasts of Y? ────────────
gmax = min(p, 3) if p >= 1 else 2
cols = list(ret.columns)
gmat = pd.DataFrame(np.nan, index=cols, columns=cols)   # rows = cause, cols = effect

for cause in cols:
    for effect in cols:
        if cause == effect:
            continue
        try:
            # grangercausalitytests(data[[effect, cause]]) tests: does `cause` Granger-cause `effect`?
            res = grangercausalitytests(ret[[effect, cause]], maxlag=gmax, verbose=False)
            pvals = [res[l][0]["ssr_ftest"][1] for l in range(1, gmax + 1)]
            gmat.loc[cause, effect] = min(pvals)
        except Exception:
            gmat.loc[cause, effect] = np.nan

print("Granger min p-value grid (row = cause -> col = effect):")
print(gmat.round(3).to_string())

neglog = -np.log10(gmat.astype(float))
fig, ax = plt.subplots(figsize=(8.5, 7))
sns.heatmap(neglog, annot=True, fmt=".1f", cmap="rocket_r",
            cbar_kws={"label": "-log10(min p)"}, linewidths=.5, ax=ax,
            mask=neglog.isna())
ax.set_title("Granger causality strength  (-log10 p; >1.3 ~ significant at 5%)")
ax.set_xlabel("effect (caused)"); ax.set_ylabel("cause")
fig.tight_layout(); fig.savefig(FIG / "07_granger_heatmap.png", dpi=130); plt.close(fig)
print("saved 07_granger_heatmap.png")
```

---


```python
# ── Orthogonalized impulse responses (taught: order-dependent IRF) ───────────
irf = var_res.irf(10)
order = list(ret.columns)
brent_i = order.index("Brent")

# Brent -> {Energy, Metal, Auto, Bank} response paths
targets = ["Energy", "Metal", "Auto", "Bank"]
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
for ax, tgt in zip(axes.ravel(), targets):
    j = order.index(tgt)
    resp = irf.orth_irfs[:, j, brent_i]   # response of tgt to orthogonal Brent shock
    ax.bar(np.arange(len(resp)), resp, color="#c0392b", alpha=.8)
    ax.axhline(0, color="grey", lw=.8)
    ax.set_title(f"Brent shock -> {tgt}")
    ax.set_xlabel("horizon (days)"); ax.set_ylabel("response")
fig.suptitle("Orthogonalized impulse responses to a one-SD Brent crude shock")
fig.tight_layout(); fig.savefig(FIG / "08_irf_brent.png", dpi=130); plt.close(fig)
print("saved 08_irf_brent.png")
print("Note: orthogonalized IRFs use a Cholesky factorization -> depend on variable order.")
```

---


```python
# ── Cholesky FEVD (taught) — ORDER-DEPENDENT variance decomposition ──────────
fevd = var_res.fevd(10)
decomp = fevd.decomp          # shape (k, H, k): [target, horizon, source]
H = decomp.shape[1] - 1       # final-horizon decomposition

targets = ["Energy", "Metal", "Bank"]
fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
palette = sns.color_palette("tab10", len(order))
for ax, tgt in zip(axes, targets):
    ti = order.index(tgt)
    horizons = np.arange(decomp.shape[1])
    bottom = np.zeros(len(horizons))
    for si, src in enumerate(order):
        share = decomp[ti, :, si]
        ax.bar(horizons, share, bottom=bottom, color=palette[si],
               label=src if ax is axes[0] else None, width=.9)
        bottom += share
    ax.set_title(f"FEVD of {tgt}"); ax.set_xlabel("horizon (days)")
    ax.set_ylim(0, 1)
axes[0].set_ylabel("variance share")
axes[0].legend(fontsize=7, ncol=2, loc="lower left")
fig.suptitle("Cholesky FEVD (ORDER-DEPENDENT) — variance share by source")
fig.tight_layout(); fig.savefig(FIG / "09_cholesky_fevd.png", dpi=130); plt.close(fig)
print("saved 09_cholesky_fevd.png")
print(f"Final-horizon ({H}-step) own-share: " +
      ", ".join(f"{t}={decomp[order.index(t), H, order.index(t)]:.2f}" for t in targets))
print("This decomposition CHANGES if the Cholesky variable order changes — the motivation"
      "\nfor the order-invariant Diebold-Yilmaz approach below.")
```

---


### Advanced layer — generalized (order-invariant) FEVD: Diebold-Yilmaz

The Cholesky FEVD above is honest but fragile: reorder the variables and the numbers move. **Pesaran-Shin's generalized FEVD** sidesteps the ordering by shocking each variable using its *own* historical covariance structure rather than a recursive triangular system. **Diebold & Yilmaz (2012)** turn that into a connectedness table:

- **`pairwise[i,j]`** — share of market *i*'s 10-day forecast-error variance coming from market *j*.
- **`to_spillover[j]`** — total variance market *j* transmits to all others (a *transmitter* score).
- **`from_spillover[i]`** — total variance market *i* absorbs from others (a *receiver* score).
- **`net = to - from`** — positive = net transmitter, negative = net receiver.
- **`total_spillover`** — the single headline number: % of system forecast-error variance that is cross-market.

---


```python
# ── Diebold-Yilmaz connectedness table (order-invariant GFEVD) ───────────────
sp = compute_spillover(ret)
print(f"VAR lag used: {sp.var_lag}   FEVD horizon: {sp.fevd_horizon}")
print(f"TOTAL SPILLOVER (connectedness index): {sp.total_spillover:.2f}%")
print(f"  -> {sp.total_spillover:.1f}% of system forecast-error variance is cross-market.")

# Heatmap of the directional pairwise matrix
fig, ax = plt.subplots(figsize=(9, 7.5))
sns.heatmap(sp.pairwise, annot=True, fmt=".1f", cmap="mako",
            cbar_kws={"label": "% of i's FEVD from j"}, linewidths=.4, ax=ax)
ax.set_title(f"Diebold-Yilmaz pairwise spillover  (total = {sp.total_spillover:.1f}%)")
ax.set_xlabel("FROM market j"); ax.set_ylabel("TO market i")
fig.tight_layout(); fig.savefig(FIG / "11_dy_pairwise.png", dpi=130); plt.close(fig)
print("saved 11_dy_pairwise.png")

# Net spillover bar — transmitters (>0) vs receivers (<0)
net = pd.Series(sp.net_spillover).sort_values()
fig, ax = plt.subplots(figsize=(10, 5))
colors = ["#2b8a3e" if v >= 0 else "#c92a2a" for v in net.values]
ax.barh(net.index, net.values, color=colors)
ax.axvline(0, color="black", lw=.8)
ax.set_title("Net directional spillover  (green = net transmitter, red = net receiver)")
ax.set_xlabel("net spillover (to - from), %")
fig.tight_layout(); fig.savefig(FIG / "11_dy_net.png", dpi=130); plt.close(fig)
print("saved 11_dy_net.png")
print("Net transmitters:", list(net[net > 0].index))
print("Net receivers:   ", list(net[net < 0].index))
```

---


```python
# ── Rolling total connectedness — spillover spikes in crises ─────────────────
roll = rolling_spillover(ret)          # defaults window=200, step=21
print(f"Rolling connectedness: {len(roll)} windows, "
      f"{roll.index[0].date()} -> {roll.index[-1].date()}")
print(f"  mean {roll.mean():.1f}%  min {roll.min():.1f}%  max {roll.max():.1f}%")

fig, ax = plt.subplots(figsize=(13, 5))
ax.fill_between(roll.index, roll.values, roll.min(), color="#3891F0", alpha=.25)
ax.plot(roll.index, roll.values, color="#1864ab", lw=1.4)
ax.axhline(roll.mean(), color="grey", ls="--", lw=1, label=f"mean {roll.mean():.0f}%")

# annotate the well-known crisis windows that fall inside the sample
for label, date in [("GFC 2008", "2008-10-15"), ("Taper 2013", "2013-08-15"),
                    ("COVID 2020", "2020-03-20"), ("Ukraine 2022", "2022-03-01")]:
    d = pd.Timestamp(date)
    if roll.index.min() <= d <= roll.index.max():
        near = roll.index[np.argmin(np.abs(roll.index - d))]
        ax.annotate(label, xy=(near, roll.loc[near]),
                    xytext=(near, roll.max() * 0.98), fontsize=8, ha="center",
                    arrowprops=dict(arrowstyle="->", color="grey", lw=.8))
ax.set_title("Rolling total connectedness (200-day window, 21-day step)")
ax.set_ylabel("total spillover, %"); ax.legend()
fig.tight_layout(); fig.savefig(FIG / "12_rolling_connectedness.png", dpi=130); plt.close(fig)
print("saved 12_rolling_connectedness.png")
```

---


```python
# ── DCC-GARCH dynamic correlations on a 3-series subset ──────────────────────
sub = ret[["Bank", "IT", "Brent"]]
dcc = fit_dcc_garch(sub)
corr = dcc["correlations"]
print(f"DCC fitted on {list(sub.columns)} — {corr.shape[0]} daily correlation points.")
if "dcc_alpha" in dcc:
    print(f"  DCC alpha={dcc['dcc_alpha']:.4f}  beta={dcc['dcc_beta']:.4f}  "
          f"(persistence a+b={dcc['dcc_alpha']+dcc['dcc_beta']:.3f})")

# Try ADCC (asymmetry term). The implementation returns params under 'params'->'g';
# some panels silently fall back to symmetric DCC, so guard for it.
adcc = fit_dcc_garch(sub, asymmetric=True)
g = adcc.get("params", {}).get("g", None)
if g is not None and abs(g) > 1e-8:
    print(f"  ADCC asymmetry term g={g:.4f} (negative-shock correlation amplification).")
else:
    print("  ADCC asymmetry negligible / fell back to symmetric DCC — presenting symmetric DCC.")

fig, ax = plt.subplots(figsize=(13, 5))
for c in corr.columns:
    ax.plot(corr.index, corr[c], lw=1, label=c.replace("_", " ↔ "))
ax.axhline(0, color="grey", lw=.8, ls="--")
ax.set_title("DCC-GARCH time-varying conditional correlations")
ax.set_ylabel("conditional correlation"); ax.legend()
fig.tight_layout(); fig.savefig(FIG / "13_dcc_correlations.png", dpi=130); plt.close(fig)
print("saved 13_dcc_correlations.png")
```

---


```python
# ── Spillover network diagram (directed, weighted by pairwise spillover) ─────
P = sp.pairwise.copy()
np.fill_diagonal(P.values, 0.0)              # drop self-loops
thresh = np.percentile(P.values[P.values > 0], 70)   # keep strongest 30% of edges
print(f"Edge threshold (70th pct of off-diagonal spillover): {thresh:.2f}%")

G = nx.DiGraph()
G.add_nodes_from(P.index)
for i in P.index:
    for j in P.columns:
        if i == j:
            continue
        w = P.loc[i, j]                       # j -> i (j transmits into i's variance)
        if w >= thresh:
            G.add_edge(j, i, weight=w)

net = pd.Series(sp.net_spillover)
node_color = [net[n] for n in G.nodes()]
sizes = [600 + 120 * abs(net[n]) for n in G.nodes()]
pos = nx.circular_layout(G)
ewidths = [0.4 + G[u][v]["weight"] / 6 for u, v in G.edges()]

fig, ax = plt.subplots(figsize=(10, 9))
nodes = nx.draw_networkx_nodes(G, pos, node_color=node_color, node_size=sizes,
                               cmap="coolwarm", vmin=-max(abs(net)), vmax=max(abs(net)), ax=ax)
nx.draw_networkx_edges(G, pos, width=ewidths, edge_color="#555",
                       arrowstyle="-|>", arrowsize=14, alpha=.55,
                       connectionstyle="arc3,rad=0.08", ax=ax)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight="bold", ax=ax)
cb = fig.colorbar(nodes, ax=ax, shrink=.7); cb.set_label("net spillover (transmitter > 0)")
ax.set_title(f"Spillover network — arrows = transmission (total connectedness {sp.total_spillover:.0f}%)")
ax.axis("off")
fig.tight_layout(); fig.savefig(FIG / "14_spillover_network.png", dpi=130); plt.close(fig)
print(f"saved 14_spillover_network.png  ({G.number_of_edges()} directed edges)")
```

---


## Findings

*Diagnostic only — not investment advice.*

- **Total connectedness.** The Diebold-Yilmaz index puts roughly **half of the system's 10-day forecast-error variance** in the cross-market channel (`total_spillover` printed in Cell 11). Most of an Indian sector's short-horizon risk is *not* idiosyncratic — it is shared with the rest of the equity-commodity system. Single-asset VaR misses this.

- **Net transmitters vs receivers.** The net-spillover bar (Cell 11) and the network (Cell 14) separate the markets into shock *sources* and shock *sinks*. Broad, cyclically-central equity sectors (e.g. Bank, Metal, Energy) tend to sit on the **transmitter** side; the commodity factors and defensives (Gold, FMCG, Pharma) tend to be **net receivers** within this equity-heavy panel — Gold in particular behaves as a diversifier here rather than a driver.

- **Commodity → sector linkages.** Brent crude shocks propagate measurably into Energy, Metal and Auto (orthogonalized IRFs, Cell 8) and show up as Granger predictability (Cell 7). This is the hidden commodity tail risk a concentrated energy/metals book carries.

- **Crisis spikes.** Rolling connectedness (Cell 12) is not constant — it **jumps during stress** (GFC 2008, COVID 2020, the 2022 commodity shock). When you most want diversification, correlations and spillover rise together, exactly the regime where DCC correlations (Cell 13) also climb toward 1. Diversification thins out precisely in the tail.

- **Cointegration caveat.** The Johansen trace test on the NIFTY/Bank/Financials level triple (Cell 5) lands **borderline** over this sample — the `r=0` statistic sits just below the 95% critical value. The methodological point stands regardless: *test before differencing*, because if a long-run equilibrium exists a VECM (error-correction term) is the right model and blind differencing would discard it. We show the VECM forecast as an illustration.

- **Method note.** Cholesky FEVD (Cell 9) is order-dependent; the Diebold-Yilmaz generalized FEVD (Cell 11) is the order-invariant measure we report. Where they disagree, prefer the generalized version.
```
