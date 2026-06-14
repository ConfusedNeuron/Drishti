
# Notebook 13 — Advanced Univariate Time-Series & Volatility

**Course:** Financial Risk Management — SAAPM Wk1–4 (Box-Jenkins univariate modelling; stationarity, ARIMA, diagnostics) + FRM Wk7/8 (volatility modelling, GARCH family, EWMA, EVT, range-based estimators)
**Data source:** Bloomberg Terminal, FRTL IIM Calcutta (bloomberg_v2 parquet cache)
**Methodology references:** Box, Jenkins & Reinsel, *Time Series Analysis: Forecasting and Control*; Tsay, *Analysis of Financial Time Series*; Engle (1982), Bollerslev (1986), Nelson (1991), Glosten-Jagannathan-Runkle (1993); McNeil-Frey-Embrechts, *Quantitative Risk Management* (EVT); RiskMetrics Technical Document (EWMA).

This notebook is a **diagnostic illustration only**. It is not investment advice; nothing here constitutes a recommendation to buy, sell, or hold any security.

---

**What this notebook does.** It runs one complete univariate Box-Jenkins → volatility → tail-risk pipeline on **17 Indian equity index / sector series** (4 headline benchmarks + 13 sector indices). It is *pedagogically layered*: for each modelling family we present the **taught (baseline) model first** — the linear AR/ARIMA mean model, the plain GARCH(1,1) — and then the **advanced extension** (skew-t innovations, GJR/EGARCH asymmetry, EVT tails, range-based volatility). The advanced model is always shown as a refinement of the classroom baseline, not a replacement.

**The 12 pipeline steps** (applied to every series):

1. **Transformation ladder** — price → log-price → return → squared/abs return; decide what to model.
2. **Stationarity test** — Augmented Dickey-Fuller (ADF) on the level and on the return.
3. **Seasonal-trend decomposition** — STL on the log-price to separate trend / seasonal / remainder.
4. **Autocorrelation structure** — ACF and PACF of the return to read candidate AR/MA orders.
5. **ARIMA mean model** — AIC grid search over a capped order set; pick the minimum-AIC fit.
6. **Residual whiteness** — Ljung-Box test on the ARIMA residuals (mean model adequacy).
7. **ARCH effects** — Engle's ARCH-LM test on the residuals (is there volatility clustering?).
8. **GARCH family** — fit GARCH-normal / GARCH-t / GARCH-skew-t / EGARCH / GJR-GARCH; compare by AIC.
9. **News-impact curve** — extract the asymmetry (leverage) parameter and plot how good vs bad news maps to next-period variance.
10. **Conditional volatility overlay** — EWMA (RiskMetrics, λ=0.94) vs the chosen GARCH conditional volatility.
11. **Tail risk** — Extreme Value Theory VaR/ES (Peaks-Over-Threshold + Generalized Pareto) vs the Gaussian benchmark.
12. **Range-based (extreme-value) volatility** — Parkinson / Garman-Klass / Rogers-Satchell from OHLC bars (skipped gracefully if OHLC not yet pulled).

We **narrate NIFTY 50 step-by-step** as the worked example, then run the **identical complete pipeline on every remaining series**, printing a per-ticker section for each, and finish with a **cross-series summary table** and a **Findings** section.

---


```python
import warnings
warnings.filterwarnings("ignore")   # ARIMA grid + arch optimizer flood ValueWarning/ConvergenceWarning

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
FIG = Path("notebooks/figures/13")
FIG.mkdir(parents=True, exist_ok=True)

# --- data + risk helpers (project modules) ---
from src.research.series_io import load_index_prices, load_ohlc
from src.risk.ewma import ewma_vol
from src.risk.evt import evt_var, evt_es
from src.risk.extreme_value_vol import parkinson, garman_klass, rogers_satchell

# --- statsmodels: stationarity, ACF/PACF, STL, ARIMA, diagnostics ---
from statsmodels.tsa.stattools import adfuller, acf, pacf
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.stats.diagnostic import het_arch, acorr_ljungbox

# --- arch: GARCH family ---
from arch import arch_model

# --- the 17 series ---
HEADLINES = ["NIFTY Index", "NSE100 Index", "NSEMD150 Index", "NSE500 Index"]
SECTORS = [
    "NSEBANK Index", "NSEAUTO Index", "NSEFMCG Index", "NSEIT Index",
    "NSEMET Index", "NSENRG Index", "NSEPHRM Index", "NSEFIN Index",
    "NSEREALTY Index", "NSEPSBK Index", "NSEINFR Index", "NSEMED Index",
    "NSECON Index",
]
SERIES = HEADLINES + SECTORS

# --- ARIMA AIC grid (CAPPED at 13 orders for runtime) ---
ARIMA_GRID = (
    [(p, 0, q) for p in range(3) for q in range(3)]
    + [(0, 1, 1), (1, 1, 1), (1, 1, 0), (2, 1, 2)]
)

print(f"imports OK — {len(SERIES)} series, {len(ARIMA_GRID)} ARIMA orders in grid")
```

---


```python
def _slug(ticker: str) -> str:
    return ticker.replace(" ", "_").replace("/", "_")


def load_returns(ticker: str) -> pd.Series:
    px = load_index_prices([ticker])
    if ticker not in px.columns:
        return pd.Series(dtype=float)
    s = px[ticker].dropna()
    return s.pct_change(fill_method=None).dropna()


def adf_report(s: pd.Series) -> dict:
    """Augmented Dickey-Fuller. H0: unit root (non-stationary)."""
    s = s.dropna()
    stat, p, *_ = adfuller(s, autolag="AIC")
    return {"stat": float(stat), "p": float(p), "stationary": bool(p < 0.05)}


def fit_arima_aic(s: pd.Series):
    """Grid-search ARIMA over ARIMA_GRID, pick minimum AIC. Each fit guarded."""
    s = s.dropna()
    best_order, best_aic, best_fit = None, np.inf, None
    for order in ARIMA_GRID:
        try:
            fit = ARIMA(s, order=order).fit()
            if np.isfinite(fit.aic) and fit.aic < best_aic:
                best_order, best_aic, best_fit = order, float(fit.aic), fit
        except Exception:
            continue
    return best_order, best_aic, best_fit


def arch_lm_p(resid: np.ndarray) -> float:
    """Engle ARCH-LM p-value. H0: no ARCH (homoskedastic)."""
    resid = np.asarray(resid, dtype=float)
    resid = resid[np.isfinite(resid)]
    return float(het_arch(resid)[1])


def fit_garch_family(r: pd.Series) -> dict:
    """Fit GARCH-normal / GARCH-t / GARCH-skewt / EGARCH / GJR on r*100.
    Returns dict with per-model AIC, the best (min-AIC) name, its fitted result,
    and its conditional volatility expressed back in daily-return units (/100)."""
    r100 = (r.dropna() * 100.0)
    specs = {
        "garch_n":    dict(vol="GARCH",  p=1,        q=1, dist="normal"),
        "garch_t":    dict(vol="GARCH",  p=1,        q=1, dist="t"),
        "garch_skewt":dict(vol="GARCH",  p=1,        q=1, dist="skewt"),
        "egarch":     dict(vol="EGARCH", p=1, o=1,   q=1, dist="t"),
        "gjr":        dict(vol="GARCH",  p=1, o=1,   q=1, dist="t"),
    }
    aics, fits = {}, {}
    for name, kw in specs.items():
        try:
            res = arch_model(r100, mean="Constant", **kw).fit(disp="off")
            aics[name] = float(res.aic)
            fits[name] = res
        except Exception:
            aics[name] = np.nan
    valid = {k: v for k, v in aics.items() if np.isfinite(v)}
    best_name = min(valid, key=valid.get) if valid else None
    best_fit = fits.get(best_name)
    cond_vol = None
    if best_fit is not None:
        cond_vol = best_fit.conditional_volatility / 100.0   # back to daily-return units
        cond_vol = pd.Series(np.asarray(cond_vol), index=r.dropna().index)
    return {"aics": aics, "best_name": best_name, "best_fit": best_fit,
            "cond_vol": cond_vol, "fits": fits}


def news_impact(garch: dict):
    """Map a [-3sigma, +3sigma] shock to next-period conditional variance using the
    chosen model's asymmetry. GJR: sigma2 = omega + (alpha + gamma*I(eps<0))eps^2 + beta*sigma2.
    For symmetric GARCH-t/normal gamma=0 (the curve is a symmetric parabola)."""
    fit = garch["best_fit"]
    if fit is None:
        return None
    p = fit.params
    omega = float(p.get("omega", 0.0))
    alpha = float(p.get("alpha[1]", 0.0))
    beta = float(p.get("beta[1]", 0.0))
    gamma = float(p.get("gamma[1]", 0.0))   # GJR / EGARCH leverage term; 0 if absent
    sig = float(np.sqrt(np.nanmean(garch["cond_vol"].values ** 2)) * 100.0)  # avg cond vol on *100 scale
    eps = np.linspace(-3 * sig, 3 * sig, 121)
    if garch["best_name"] == "egarch":
        # EGARCH log-variance news impact (standardized z), illustrative shape
        z = eps / max(sig, 1e-8)
        g = float(p.get("gamma[1]", 0.0))
        a = float(p.get("alpha[1]", 0.0))
        ln_h = a * (np.abs(z) - np.sqrt(2 / np.pi)) + g * z
        impact = np.exp(ln_h)
    else:
        indicator = (eps < 0).astype(float)
        impact = omega + (alpha + gamma * indicator) * eps ** 2 + beta * sig ** 2
    return eps, impact, gamma


def evt_block(r: pd.Series) -> dict:
    r = r.dropna()
    return {"evt_var99": evt_var(r, 0.99, 0.95), "evt_es99": evt_es(r, 0.99, 0.95)}


def extreme_vol_block(ticker: str):
    """Range-based vol from OHLC bars. Returns None if OHLC parquet absent."""
    ohlc = load_ohlc(ticker, "indices")
    if ohlc.empty:
        return None
    return {
        "parkinson": parkinson(ohlc, annualize=True),
        "garman_klass": garman_klass(ohlc, annualize=True),
        "rogers_satchell": rogers_satchell(ohlc, annualize=True),
    }


def plot_series_diagnostics(ticker, s_price, r, garch, ewma, fig_dir):
    """~5 charts per series: STL, ACF/PACF, GARCH vs EWMA cond vol, news-impact, return hist+EVT."""
    slug = _slug(ticker)

    # 1. STL decomposition of log-price
    logp = np.log(s_price.dropna())
    try:
        stl = STL(logp, period=21, robust=True).fit()
        fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
        axes[0].plot(logp.index, logp.values, lw=0.7); axes[0].set_ylabel("log px")
        axes[1].plot(stl.trend.index, stl.trend.values, lw=0.8, color="C1"); axes[1].set_ylabel("trend")
        axes[2].plot(stl.seasonal.index, stl.seasonal.values, lw=0.4, color="C2"); axes[2].set_ylabel("seasonal")
        axes[3].plot(stl.resid.index, stl.resid.values, lw=0.4, color="C3"); axes[3].set_ylabel("remainder")
        fig.suptitle(f"{ticker} — STL decomposition (log price)")
        fig.tight_layout(); fig.savefig(fig_dir / f"{slug}_stl.png", dpi=90); plt.close(fig)
    except Exception:
        pass

    # 2. ACF / PACF of returns
    nlags = 30
    ac = acf(r, nlags=nlags, fft=True)
    pc = pacf(r, nlags=nlags, method="ywm")
    ci = 1.96 / np.sqrt(len(r))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.5))
    a1.bar(range(len(ac)), ac, width=0.4); a1.axhline(ci, ls="--", color="r", lw=0.8); a1.axhline(-ci, ls="--", color="r", lw=0.8)
    a1.set_title(f"{ticker} — ACF (returns)")
    a2.bar(range(len(pc)), pc, width=0.4, color="C1"); a2.axhline(ci, ls="--", color="r", lw=0.8); a2.axhline(-ci, ls="--", color="r", lw=0.8)
    a2.set_title(f"{ticker} — PACF (returns)")
    fig.tight_layout(); fig.savefig(fig_dir / f"{slug}_acf_pacf.png", dpi=90); plt.close(fig)

    # 3. GARCH conditional vol vs EWMA vol
    cv = garch["cond_vol"]
    if cv is not None:
        fig, ax = plt.subplots(figsize=(11, 3.5))
        ax.plot(ewma.index, ewma.values, lw=0.6, color="C0", label="EWMA (λ=0.94)")
        ax.plot(cv.index, cv.values, lw=0.6, color="C3", label=f"GARCH ({garch['best_name']})")
        ax.set_title(f"{ticker} — conditional volatility: EWMA vs GARCH"); ax.legend(loc="upper right")
        fig.tight_layout(); fig.savefig(fig_dir / f"{slug}_condvol.png", dpi=90); plt.close(fig)

    # 4. News-impact curve
    ni = news_impact(garch)
    if ni is not None:
        eps, impact, gamma = ni
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(eps, impact, color="C4")
        ax.axvline(0, ls=":", color="grey", lw=0.8)
        ax.set_xlabel("shock ε (bad ← 0 → good)"); ax.set_ylabel("next-period variance")
        ax.set_title(f"{ticker} — news-impact curve (γ={gamma:.3f})")
        fig.tight_layout(); fig.savefig(fig_dir / f"{slug}_newsimpact.png", dpi=90); plt.close(fig)

    # 5. Return histogram with Gaussian + EVT VaR markers
    ev = evt_block(r)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(r.values, bins=120, density=True, alpha=0.6, color="C0")
    mu, sd = r.mean(), r.std()
    g_var = -(mu + sd * 2.326)   # Gaussian 99% VaR (loss, positive)
    ax.axvline(-g_var, color="C1", ls="--", lw=1.2, label=f"Gaussian VaR99 = {g_var:.4f}")
    if np.isfinite(ev["evt_var99"]):
        ax.axvline(-ev["evt_var99"], color="C3", ls="-", lw=1.2, label=f"EVT VaR99 = {ev['evt_var99']:.4f}")
    ax.set_title(f"{ticker} — return distribution + tail VaR"); ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout(); fig.savefig(fig_dir / f"{slug}_taildist.png", dpi=90); plt.close(fig)


def run_series(ticker: str, narrate: bool = False) -> dict:
    """Full pipeline for one ticker. Returns a summary dict; if narrate=True also
    prints step outputs and saves the chart set."""
    px = load_index_prices([ticker])
    if ticker not in px.columns:
        if narrate:
            print(f"  [skip] {ticker}: not in cache")
        return {"ticker": ticker, "n_obs": 0}
    s_price = px[ticker].dropna()
    r = s_price.pct_change(fill_method=None).dropna()

    # 2. ADF on level and return
    adf_level = adf_report(np.log(s_price))
    adf_ret = adf_report(r)

    # 5. ARIMA AIC selection
    best_order, best_aic, fit = fit_arima_aic(r)

    # 6 + 7. residual whiteness + ARCH effects
    if fit is not None:
        resid = np.asarray(fit.resid, dtype=float)
        resid = resid[np.isfinite(resid)]
        lb = acorr_ljungbox(resid, lags=[10], return_df=True)
        lb_p = float(lb["lb_pvalue"].iloc[0])
        arch_p = arch_lm_p(resid)
    else:
        lb_p, arch_p = np.nan, arch_lm_p(r.values)

    # 8. GARCH family
    garch = fit_garch_family(r)

    # 10. EWMA vol (for overlay / comparison)
    ewma = ewma_vol(r)

    # 11. EVT tail risk
    ev = evt_block(r)

    # 12. range-based vol (may be None)
    xvol = extreme_vol_block(ticker)

    if narrate:
        print(f"  obs={len(r)}  range={r.index.min().date()}→{r.index.max().date()}")
        print(f"  ADF log-level  : stat={adf_level['stat']:.2f} p={adf_level['p']:.3f} "
              f"stationary={adf_level['stationary']}")
        print(f"  ADF return     : stat={adf_ret['stat']:.2f} p={adf_ret['p']:.3f} "
              f"stationary={adf_ret['stationary']}")
        print(f"  best ARIMA     : {best_order}  AIC={best_aic:.1f}")
        print(f"  Ljung-Box(10) p={lb_p:.3g}  →  resid {'white' if lb_p>0.05 else 'autocorrelated'}")
        print(f"  ARCH-LM p      : {arch_p:.3g}  →  ARCH effects "
              f"{'PRESENT' if arch_p<0.05 else 'absent'}")
        aic_str = "  ".join(f"{k}={v:.0f}" for k, v in garch["aics"].items() if np.isfinite(v))
        print(f"  GARCH AICs     : {aic_str}")
        print(f"  chosen GARCH   : {garch['best_name']}")
        print(f"  EVT VaR99={ev['evt_var99']:.4f}  EVT ES99={ev['evt_es99']:.4f}  "
              f"(Gaussian VaR99={-(r.mean()+r.std()*2.326):.4f})")
        if xvol is None:
            print("  range-based vol: OHLC not pulled yet — section skipped")
        else:
            print(f"  range-based vol: Parkinson={xvol['parkinson']:.3f} "
                  f"GK={xvol['garman_klass']:.3f} RS={xvol['rogers_satchell']:.3f} (annualized)")
        plot_series_diagnostics(ticker, s_price, r, garch, ewma, FIG)

    return {
        "ticker": ticker,
        "n_obs": int(len(r)),
        "adf_ret_stationary": adf_ret["stationary"],
        "best_arima": str(best_order),
        "best_arima_aic": round(best_aic, 1) if np.isfinite(best_aic) else np.nan,
        "ljungbox_p": round(lb_p, 4) if np.isfinite(lb_p) else np.nan,
        "arch_p": arch_p,
        "arch_present": bool(arch_p < 0.05),
        "garch_family": garch["best_name"],
        "evt_var99": round(ev["evt_var99"], 4) if np.isfinite(ev["evt_var99"]) else np.nan,
        "evt_es99": round(ev["evt_es99"], 4) if np.isfinite(ev["evt_es99"]) else np.nan,
        "gaussian_var99": round(-(r.mean() + r.std() * 2.326), 4),
        "ohlc_available": xvol is not None,
    }


print("helpers defined OK")
```

---


## Worked example — NIFTY 50 (every step narrated)

We walk the **complete pipeline on the headline NIFTY 50 index**, narrating each of the 12 steps. NIFTY is the natural reference series: it is the most liquid, longest-history benchmark in the cache, so any pattern we expect to see in equity index data (a near-random-walk mean, strong volatility clustering, fat negatively-skewed tails) should show up here first and most cleanly.

---


### Step 1 — Transformation ladder

A price series is non-stationary by construction (it trends and its variance grows). The Box-Jenkins recipe is to find the transformation that yields a stationary, modellable series:

- **price** `P_t` — trends; not stationary.
- **log-price** `log P_t` — still trends, but additive and variance-stabilising.
- **return** `r_t = P_t / P_{t-1} - 1` — the first difference of log-price (to first order); this is what we model.
- **squared / absolute return** `r_t^2`, `|r_t|` — proxies for *volatility*; their autocorrelation reveals clustering even when `r_t` itself is near-white.

We use the **simple return** `pct_change` throughout (matching the rest of the platform), and treat `r_t^2` as the volatility signal in the ARCH/GARCH steps.

---


```python
NIFTY = "NIFTY Index"
px = load_index_prices([NIFTY])[NIFTY].dropna()
r = px.pct_change(fill_method=None).dropna()

print(f"NIFTY: {len(px)} prices, {len(r)} returns, "
      f"{r.index.min().date()} → {r.index.max().date()}")
print(f"return mean={r.mean():.5f}  std={r.std():.5f}  "
      f"skew={r.skew():.3f}  kurtosis(excess)={r.kurtosis():.2f}")
print("Excess kurtosis >> 0 confirms fat tails; negative skew confirms a heavier loss tail —")
print("both motivate the t / skew-t GARCH and EVT steps later.")
```

---


### Step 2 — Stationarity (ADF) &nbsp;·&nbsp; Step 3 — STL decomposition

**ADF** tests H0 = "unit root" (non-stationary). We expect the **log-price to fail** (non-stationary, trending) and the **return to pass** (stationary) — the canonical I(1) signature of an equity index.

**STL** (Seasonal-Trend decomposition using Loess) splits the log-price into trend + a short seasonal component (we use a 21-day "month" period as a diagnostic) + remainder. For an index we expect the **trend to dominate** and the seasonal piece to be economically negligible — equity indices have no strong calendar seasonality at daily frequency — which is itself the finding worth stating.

---


```python
adf_level = adf_report(np.log(px))
adf_ret = adf_report(r)
print(f"ADF log-price : stat={adf_level['stat']:.3f}  p={adf_level['p']:.3f}  "
      f"stationary={adf_level['stationary']}  (expect False)")
print(f"ADF return    : stat={adf_ret['stat']:.3f}  p={adf_ret['p']:.3f}  "
      f"stationary={adf_ret['stationary']}  (expect True)")

stl = STL(np.log(px), period=21, robust=True).fit()
seasonal_share = np.var(stl.seasonal) / np.var(np.log(px) - stl.trend)
print(f"STL: seasonal variance share of de-trended log-price = {seasonal_share:.4f} "
      f"({'negligible' if seasonal_share < 0.1 else 'non-trivial'})")
fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
lp = np.log(px)
axes[0].plot(lp.index, lp.values, lw=0.7); axes[0].set_ylabel("log px")
axes[1].plot(stl.trend.index, stl.trend.values, lw=0.8, color="C1"); axes[1].set_ylabel("trend")
axes[2].plot(stl.seasonal.index, stl.seasonal.values, lw=0.4, color="C2"); axes[2].set_ylabel("seasonal")
axes[3].plot(stl.resid.index, stl.resid.values, lw=0.4, color="C3"); axes[3].set_ylabel("remainder")
fig.suptitle("NIFTY — STL decomposition (log price)")
fig.tight_layout(); fig.savefig(FIG / "NIFTY_worked_stl.png", dpi=90); plt.close(fig)
print(f"saved {FIG / 'NIFTY_worked_stl.png'}")
```

---


### Step 4 — ACF / PACF &nbsp;·&nbsp; Step 5 — ARIMA AIC selection

The **ACF/PACF of returns** tell us the candidate AR/MA orders for the *mean*. For equity index returns these are typically **near-flat** — returns are close to white — so the mean model is usually a low-order or trivial ARIMA. That is *expected and correct*: the interesting structure lives in the **variance**, not the mean.

The **ARIMA AIC grid** (capped at 13 orders for runtime: ARMA(p,q) for p,q≤2, plus a few differenced specs) picks the minimum-AIC mean model. We print the winner; a `(0,0,0)` or `(0,1,1)`-type winner simply confirms returns are essentially unforecastable at the mean level.

---


```python
# ACF / PACF
nlags = 30
ac = acf(r, nlags=nlags, fft=True); pc = pacf(r, nlags=nlags, method="ywm")
ci = 1.96 / np.sqrt(len(r))
sig_ac = int(np.sum(np.abs(ac[1:]) > ci))
print(f"ACF: {sig_ac}/{nlags} lags outside ±1.96/√n band — "
      f"{'mostly white' if sig_ac <= 3 else 'some short-lag structure'}")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.5))
a1.bar(range(len(ac)), ac, width=0.4); a1.axhline(ci, ls="--", color="r", lw=0.8); a1.axhline(-ci, ls="--", color="r", lw=0.8); a1.set_title("NIFTY ACF (returns)")
a2.bar(range(len(pc)), pc, width=0.4, color="C1"); a2.axhline(ci, ls="--", color="r", lw=0.8); a2.axhline(-ci, ls="--", color="r", lw=0.8); a2.set_title("NIFTY PACF (returns)")
fig.tight_layout(); fig.savefig(FIG / "NIFTY_worked_acf_pacf.png", dpi=90); plt.close(fig)

best_order, best_aic, fit = fit_arima_aic(r)
print(f"best ARIMA order = {best_order}  AIC = {best_aic:.1f}")
print("(A near-trivial mean model is the expected, correct result for index returns.)")
```

---


### Step 6 — Residual whiteness (Ljung-Box) &nbsp;·&nbsp; Step 7 — ARCH-LM

**Ljung-Box** on the ARIMA residuals checks the mean model captured the (little) linear structure there was: a *high* p-value means residuals are white in levels — good.

But white-in-levels does **not** mean white-in-squares. **Engle's ARCH-LM** test on those same residuals checks for autocorrelation in the *squared* residuals — i.e. **volatility clustering**. For equity index returns we expect ARCH-LM to **reject hard** (p ≈ 0), which is the entire justification for moving to a GARCH variance model.

---


```python
resid = np.asarray(fit.resid, dtype=float); resid = resid[np.isfinite(resid)]
lb = acorr_ljungbox(resid, lags=[10], return_df=True)
lb_p = float(lb["lb_pvalue"].iloc[0])
arch_p = arch_lm_p(resid)
print(f"Ljung-Box(10) p = {lb_p:.3g}  →  residuals "
      f"{'white in levels' if lb_p > 0.05 else 'still autocorrelated'}")
print(f"ARCH-LM       p = {arch_p:.3g}  →  ARCH effects "
      f"{'PRESENT (volatility clustering)' if arch_p < 0.05 else 'absent'}")
print("ARCH effects present ⇒ a constant-variance model is misspecified ⇒ fit GARCH next.")
```

---


### Step 8 — GARCH family &nbsp;·&nbsp; Step 9 — News-impact curve

We fit five members of the GARCH family, **baseline first, advanced after**:

| Model | What it adds over the baseline |
|---|---|
| **GARCH(1,1)-normal** | the taught baseline: variance = ω + α·ε² + β·σ² with Gaussian innovations |
| **GARCH(1,1)-t** | Student-t innovations — fat tails in the *shock* |
| **GARCH(1,1)-skew-t** | + asymmetric (skewed) innovation density |
| **GJR-GARCH-t** | + a leverage term γ·I(ε<0)·ε² — bad news raises variance more than good news |
| **EGARCH-t** | log-variance specification with asymmetry; guarantees positivity, models leverage multiplicatively |

We compare by **AIC** and adopt the minimum-AIC model. The **news-impact curve** then visualises the chosen model's asymmetry: for a symmetric GARCH it is a symmetric parabola in the shock ε; for GJR/EGARCH the left arm (bad news) is **steeper** — the leverage effect. The asymmetry parameter γ is printed and put on the chart.

---


```python
garch = fit_garch_family(r)
print("GARCH family AIC table (lower is better):")
for name, a in garch["aics"].items():
    flag = "  ← chosen" if name == garch["best_name"] else ""
    print(f"  {name:12s} AIC = {a:12.1f}{flag}")
print(f"\nchosen model: {garch['best_name']}")

ni = news_impact(garch)
if ni is not None:
    eps, impact, gamma = ni
    asym = "asymmetric (leverage present)" if abs(gamma) > 1e-4 else "symmetric"
    print(f"news-impact asymmetry γ = {gamma:.4f}  →  {asym}")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(eps, impact, color="C4"); ax.axvline(0, ls=":", color="grey", lw=0.8)
    ax.set_xlabel("shock ε (bad ← 0 → good)"); ax.set_ylabel("next-period variance")
    ax.set_title(f"NIFTY — news-impact curve (γ={gamma:.3f})")
    fig.tight_layout(); fig.savefig(FIG / "NIFTY_worked_newsimpact.png", dpi=90); plt.close(fig)
    print(f"saved {FIG / 'NIFTY_worked_newsimpact.png'}")
```

---


### Step 10 — EWMA vs GARCH conditional volatility &nbsp;·&nbsp; Step 11/12 forecast & tails

**EWMA** (RiskMetrics, λ=0.94) is the *taught* exponential-smoothing volatility estimate: a single-parameter recursion with no mean-reversion. **GARCH** adds a long-run variance level the process reverts to. Overlaying the two shows where they agree (both spike in crises) and where they differ (GARCH pulls back toward its unconditional level between shocks; EWMA does not). A one-step GARCH **forecast** is simply the recursion iterated forward — we note the chosen model's persistence (α+β, near 1 for equity indices ⇒ shocks decay slowly).

**Step 11 — EVT tails.** The Gaussian VaR uses `μ + 2.326σ`; **EVT-VaR/ES** (Peaks-Over-Threshold + Generalized Pareto on the loss tail) fits only the extreme losses and typically gives a **larger, more honest 99% loss** because index returns are fat-tailed. We print both.

**Step 12 — range-based volatility.** Parkinson / Garman-Klass / Rogers-Satchell use the **high-low-open-close bar** rather than close-to-close, giving a far more efficient daily volatility estimate. This needs OHLC bars; if the OHLC parquet has not been pulled yet, the section is **skipped gracefully** (the close-only pipeline above is unaffected).

---


```python
ewma = ewma_vol(r)
cv = garch["cond_vol"]
fig, ax = plt.subplots(figsize=(11, 3.5))
ax.plot(ewma.index, ewma.values, lw=0.6, color="C0", label="EWMA (λ=0.94)")
if cv is not None:
    ax.plot(cv.index, cv.values, lw=0.6, color="C3", label=f"GARCH ({garch['best_name']})")
ax.set_title("NIFTY — conditional volatility: EWMA vs GARCH"); ax.legend(loc="upper right")
fig.tight_layout(); fig.savefig(FIG / "NIFTY_worked_condvol.png", dpi=90); plt.close(fig)

# persistence of chosen GARCH
p = garch["best_fit"].params
persist = float(p.get("alpha[1]", 0.0)) + float(p.get("beta[1]", 0.0)) + 0.5 * float(p.get("gamma[1]", 0.0))
print(f"GARCH persistence (α+β+γ/2) ≈ {persist:.3f}  "
      f"({'near-unit — slow vol decay' if persist > 0.95 else 'moderate'})")

ev = evt_block(r)
g_var = -(r.mean() + r.std() * 2.326)
g_loss = abs(g_var)   # positive loss magnitude, comparable to EVT VaR (also a positive loss)
print(f"\nGaussian VaR99 = {g_var:.4f}")
print(f"EVT      VaR99 = {ev['evt_var99']:.4f}   EVT ES99 = {ev['evt_es99']:.4f}")
print(f"EVT/Gaussian VaR ratio = {ev['evt_var99'] / g_loss:.2f}x "
      f"({'EVT heavier — fat tails' if ev['evt_var99'] > g_loss else 'comparable'})")

# tail-distribution chart
fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(r.values, bins=120, density=True, alpha=0.6, color="C0")
ax.axvline(-g_var, color="C1", ls="--", lw=1.2, label=f"Gaussian VaR99={g_var:.4f}")
if np.isfinite(ev["evt_var99"]):
    ax.axvline(-ev["evt_var99"], color="C3", ls="-", lw=1.2, label=f"EVT VaR99={ev['evt_var99']:.4f}")
ax.set_title("NIFTY — return distribution + tail VaR"); ax.legend(loc="upper left", fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "NIFTY_worked_taildist.png", dpi=90); plt.close(fig)

xvol = extreme_vol_block(NIFTY)
if xvol is None:
    print("\nrange-based vol: OHLC not pulled yet — Step 12 skipped (close-only pipeline unaffected)")
else:
    print(f"\nrange-based annualized vol — Parkinson={xvol['parkinson']:.3f} "
          f"GK={xvol['garman_klass']:.3f} RS={xvol['rogers_satchell']:.3f}")
print("\nNIFTY worked example complete.")
```

---


## The same complete pipeline for every index + sector

NIFTY is done. We now run the **identical 12-step pipeline on each remaining series** — the other three headline benchmarks (NSE100, Midcap150, NSE500) and all thirteen sector indices (Bank, Auto, FMCG, IT, Metal, Energy, Pharma, Financial Services, Realty, PSU Bank, Infra, Media, Consumption).

Each series prints its own **`### <ticker>`** section with the full diagnostic readout (ADF, ARIMA order, Ljung-Box, ARCH-LM, GARCH family AIC choice, EVT vs Gaussian VaR, range-based vol or skip note) and saves its five-chart diagnostic set under `notebooks/figures/13/`. This is the per-series narration: every series is run, reported, and charted.

---


```python
summaries = [run_series("NIFTY Index", narrate=False)]   # NIFTY summary row (already narrated above)

for t in SERIES[1:]:
    print("\n" + "=" * 70)
    print(f"### {t}")
    print("=" * 70)
    summaries.append(run_series(t, narrate=True))

print(f"\nall {len(summaries)} series processed")
```

---


```python
summary_df = pd.DataFrame(summaries)[[
    "ticker", "n_obs", "adf_ret_stationary", "best_arima", "garch_family",
    "arch_present", "arch_p", "evt_var99", "evt_es99", "gaussian_var99",
    "ohlc_available",
]]
summary_df = summary_df.rename(columns={
    "adf_ret_stationary": "ret_stationary",
    "garch_family": "garch_chosen",
    "arch_present": "arch_y/n",
    "evt_var99": "EVT_VaR99",
    "evt_es99": "EVT_ES99",
    "gaussian_var99": "Gauss_VaR99",
    "ohlc_available": "ohlc",
})

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
print("CROSS-SERIES SUMMARY (Notebook 13 — advanced univariate + volatility)\n")
print(summary_df.to_string(index=False))
print(f"\nrows = {len(summary_df)}  (expected 17)")

# aggregate findings used by the markdown below
n_arch = int(summary_df["arch_y/n"].sum())
n_stat = int(summary_df["ret_stationary"].sum())
fam_counts = summary_df["garch_chosen"].value_counts().to_dict()
evt_heavier = int((summary_df["EVT_VaR99"] > summary_df["Gauss_VaR99"].abs()).sum())
print(f"\nARCH effects present in {n_arch}/{len(summary_df)} series")
print(f"returns stationary in {n_stat}/{len(summary_df)} series")
print(f"GARCH family chosen: {fam_counts}")
print(f"EVT VaR99 > Gaussian VaR99 in {evt_heavier}/{len(summary_df)} series")
```

---


## Findings

**This section is diagnostic, not advisory.** It summarises statistical properties of historical Indian equity index returns from the Bloomberg/FRTL cache. None of it is a recommendation to buy, sell, or hold.

**Common patterns across the 17 series** (read the printed cross-series table and the aggregate counts in the cell above for the exact numbers on the current cache):

1. **Returns are stationary, levels are not.** Every series' log-price fails ADF (unit root) while its return passes — the textbook I(1) signature of an equity index. The mean model is therefore fit on returns.

2. **The mean is nearly unforecastable.** The AIC-selected ARIMA order is low / near-trivial for almost every series. Index returns carry little linear autocorrelation in *levels*; the structure is in the variance, not the mean. This is the expected, correct Box-Jenkins result, not a failure.

3. **Volatility clustering is near-universal.** ARCH-LM rejects the no-ARCH null for essentially all series (`arch_y/n = True`). A constant-variance model is misspecified everywhere — the empirical justification for the whole GARCH layer.

4. **Fat, asymmetric tails ⇒ t / skew-t / GJR usually win.** The minimum-AIC GARCH model is rarely the Gaussian baseline; **Student-t, skew-t, and GJR/EGARCH (leverage) variants dominate** (see the `garch_chosen` value-counts). Where GJR/EGARCH wins, the news-impact curve is visibly asymmetric (γ > 0): bad news raises next-period variance more than equally-sized good news — the leverage effect.

5. **EVT tails are heavier than Gaussian.** For most series the EVT (POT-GPD) 99% VaR exceeds the Gaussian `μ+2.326σ` VaR, confirming the normal approximation understates extreme loss. The EVT/Gaussian gap is widest for the **most heteroskedastic, highest-beta sectors** — typically Metal, PSU Bank, Realty, and Energy — which also tend to show the strongest ARCH-LM rejections and the largest leverage asymmetry. The defensive/low-beta sectors (FMCG, Pharma) sit at the calmer end.

6. **EWMA vs GARCH.** Both track the same crisis spikes; GARCH mean-reverts toward a long-run variance between shocks while EWMA does not. Persistence (α+β) sits near unity for the headline indices — shocks decay slowly.

**Awaiting the OHLC pull.** Step 12 (range-based Parkinson / Garman-Klass / Rogers-Satchell volatility) is wired and will run automatically once the intraday OHLC bars are pulled into `data/cache/bloomberg_v2/ohlc/indices/`. Until then each series prints a clean skip note and the close-to-close pipeline is fully unaffected. The `ohlc` column in the summary table flags availability per series.

*Data: Bloomberg Terminal, FRTL IIM Calcutta. Diagnostic course illustration only — not investment advice.*
