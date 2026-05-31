# Notebook 04 — HMM Volatility Regime Detection
> Run in: **BQuant (Bloomberg hosted Python environment at FRTL)**
> Inputs: `equities_returns.parquet`, `macro_series.parquet` (from Notebook 01)
> Output artifacts: `regime_history.parquet`, `hmm_params.json`

---

## Cell 1 [MARKDOWN]

# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti computes multi-method market risk and researches commodity spillover into Indian equity sectors. A key insight from this research is that volatility is not constant — markets alternate between calm, low-volatility regimes and turbulent, high-volatility regimes. The VaR model that ignores this regime structure will systematically understate risk in bad times and overstate it in calm times.

The HMM regime labels produced by this notebook allow Drishti to:
1. Report **regime-conditioned VaR**: separate VaR estimates for high-vol and low-vol regimes, so the displayed risk is calibrated to the current market environment.
2. Condition IC/Granger analysis on regime: test whether factor signals are stronger in high-vol regimes.
3. Explain Christoffersen test failures: violation clustering is a signature of unmodeled regime switching.

---

## Cell 2 [MARKDOWN]

## Notebook 04 — HMM Volatility Regime Detection

**What this notebook does:**

Fits a **2-state Gaussian Hidden Markov Model** on daily return features to classify each trading day as either a low-volatility regime (State 0) or a high-volatility regime (State 1).

**Model:**
- Type: `GaussianHMM(n_components=2, covariance_type="full")`
- Library: `hmmlearn`
- Features: rolling 20-day portfolio volatility, rolling 20-day mean absolute return, India VIX level, India VIX 5-day change
- Fitting: **walk-forward** — at each monthly refit point, the model is fitted on all past data and used to predict the *next* month's regimes. This prevents lookahead bias.

**Critical design decision — canonical labeling:**
HMM does not guarantee which state number corresponds to which economic regime. After each refit, states are relabeled so that *State 0 always = lowest rolling-vol emission mean* (low-vol regime). Without this, states can flip label between refits, making the regime history discontinuous.

**Validation:**
- High-vol regime should capture COVID Feb-Apr 2020 and 2022 drawdown period.
- Regime-conditioned VaR: high-vol VaR should be meaningfully larger than low-vol VaR.
- OOS breach rate per regime should be close to 1% at 99% confidence.

---

## Cell 3 [CODE]

```python
# ── Imports ────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM
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
# ── Load data ────────────────────────────────────────────────────────────────
equity_returns = pd.read_parquet(INPUT_DIR / "equities_returns.parquet")
macro_returns  = pd.read_parquet(INPUT_DIR / "macro_series.parquet")

# Build an equal-weighted NIFTY 50 portfolio return series as the HMM input
# (In production, use actual portfolio weights from Zerodha import)
portfolio_returns = equity_returns.mean(axis=1)
portfolio_returns.name = "portfolio"

vix = macro_returns["indiavix"].copy()   # India VIX level

print(f"Portfolio returns: {len(portfolio_returns)} days")
print(f"Ann. vol (full sample): {portfolio_returns.std()*252**0.5:.2%}")
```

---

## Cell 5 [MARKDOWN]

### Build HMM features

The four features capture different aspects of the volatility regime:
- **rolling_vol**: 20-day rolling std × √252 — the core regime signal
- **rolling_abs_ret**: 20-day rolling mean |return| — complements vol; captures jump days
- **vix_level**: India VIX — forward-looking implied vol; leads realized vol
- **vix_change**: 5-day VIX change — regime *transitions* show up as VIX spikes

All features are standardized (z-scored) so the HMM covariance matrix isn't dominated by scale differences between features.

---

## Cell 6 [CODE]

```python
# ── Build HMM feature matrix ─────────────────────────────────────────────────
WINDOW = 20   # rolling window for vol estimation

features = pd.DataFrame(index=portfolio_returns.index)

features["rolling_vol"]    = portfolio_returns.rolling(WINDOW).std() * np.sqrt(252)
features["rolling_abs_ret"]= portfolio_returns.abs().rolling(WINDOW).mean()

# Align VIX to portfolio dates; forward-fill small gaps
vix_aligned = vix.reindex(portfolio_returns.index).ffill()
features["vix_level"]  = vix_aligned
features["vix_change"] = vix_aligned.diff(5)

features = features.dropna()

# Standardize so HMM covariance matrix is well-conditioned
from sklearn.preprocessing import StandardScaler
scaler  = StandardScaler()
X_scaled = scaler.fit_transform(features.values)

print(f"Feature matrix: {X_scaled.shape} (obs × features)")
print(f"Features: {list(features.columns)}")
print(f"\nFeature summary (raw):")
print(features.describe().round(4))
```

---

## Cell 7 [MARKDOWN]

### Canonical state labeling

HMM state numbering is arbitrary — State 0 might be high-vol in one run and low-vol in another. After each `model.fit()`, we sort states by their emission mean on `rolling_vol` (the first feature after scaling, which corresponds to index 0). The state with the lowest `rolling_vol` mean becomes State 0 (low-vol) and the state with the highest becomes State 1 (high-vol).

This must be applied after *every* refit in the walk-forward loop — not just once at the end.

---

## Cell 8 [CODE]

```python
# ── Canonical labeling helper ────────────────────────────────────────────────

def canonical_labels(model: GaussianHMM, states: np.ndarray,
                     vol_feature_idx: int = 0) -> tuple[np.ndarray, dict]:
    """
    Remap HMM states so State 0 = lowest vol emission mean.

    Parameters
    ----------
    model            : fitted GaussianHMM
    states           : raw predicted state sequence
    vol_feature_idx  : column index of rolling_vol in the feature matrix

    Returns
    -------
    relabeled_states : ndarray with canonical labels
    state_map        : {original_state: canonical_state}
    """
    emission_means = model.means_[:, vol_feature_idx]   # vol mean per state
    sort_order     = np.argsort(emission_means)          # ascending → State 0 = low vol
    state_map      = {int(sort_order[i]): i for i in range(len(sort_order))}
    relabeled      = np.array([state_map[int(s)] for s in states])
    return relabeled, state_map


print("Canonical labeling function defined.")
```

---

## Cell 9 [MARKDOWN]

### Walk-forward HMM fitting

The walk-forward procedure prevents lookahead bias:
- **Minimum training window:** 252 trading days (~1 year) before making any OOS predictions
- **Refit frequency:** every 21 trading days (~1 month)
- **Prediction:** after each refit, predict regimes for the *next* 21 days (OOS)
- **Stored:** only OOS predictions — in-sample labels are discarded

This mirrors how a risk manager would operate: the model is retrained monthly on all available history, then deployed for the next month.

---

## Cell 10 [CODE]

```python
# ── Walk-forward HMM ─────────────────────────────────────────────────────────
MIN_TRAIN = 252    # minimum days of history before first OOS prediction
REFIT_FREQ = 21    # retrain every ~1 month of trading days
N_STATES   = 2
N_ITER     = 200   # EM iterations per fit
SEED       = 42

n = len(features)
oos_results = {}   # {date: {"regime": int, "prob_high_vol": float}}

print("Running walk-forward HMM fitting...")

t = MIN_TRAIN
while t < n:
    # Fit on all data up to t (expanding window)
    X_train = X_scaled[:t]

    try:
        model = GaussianHMM(
            n_components=N_STATES,
            covariance_type="full",
            n_iter=N_ITER,
            random_state=SEED,
        )
        model.fit(X_train)
    except Exception as e:
        print(f"  Fit failed at t={t}: {e}")
        t += REFIT_FREQ
        continue

    # Predict OOS: next REFIT_FREQ days
    oos_end    = min(t + REFIT_FREQ, n)
    X_oos      = X_scaled[t:oos_end]
    raw_states = model.predict(X_oos)
    probs      = model.predict_proba(X_oos)

    # Apply canonical labeling to this refit's predictions
    labeled_states, state_map = canonical_labels(model, raw_states)

    # Store results keyed by date
    oos_dates = features.index[t:oos_end]
    for i, date in enumerate(oos_dates):
        # prob_high_vol = probability of State 1 (high vol) after relabeling
        high_vol_orig = [k for k, v in state_map.items() if v == 1]
        p_high = float(probs[i, high_vol_orig[0]]) if high_vol_orig else 0.5
        oos_results[date] = {
            "regime":       int(labeled_states[i]),
            "prob_high_vol": p_high,
        }

    t = oos_end
    if t % (REFIT_FREQ * 6) == 0 or t >= n:
        print(f"  Progress: {t}/{n} days processed")

print(f"\nWalk-forward complete. OOS labels: {len(oos_results)} days")
```

---

## Cell 11 [MARKDOWN]

### Regime history analysis

Verify that the HMM captures known stress periods:
- **COVID crash (Feb–Apr 2020):** should be classified as high-vol (State 1)
- **2022 drawdown (Jan–Jun 2022):** should be classified as high-vol

If the model misses these, reconsider features or the number of states.

---

## Cell 12 [CODE]

```python
# ── Build regime history DataFrame ───────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

regime_history = pd.DataFrame(oos_results).T
regime_history.index = pd.DatetimeIndex(regime_history.index)
regime_history["regime"]        = regime_history["regime"].astype(int)
regime_history["prob_high_vol"] = regime_history["prob_high_vol"].astype(float)

# Fraction of time in each regime
frac_high = (regime_history["regime"] == 1).mean()
frac_low  = (regime_history["regime"] == 0).mean()
print(f"High-vol regime (State 1): {frac_high:.1%} of OOS days")
print(f"Low-vol  regime (State 0): {frac_low:.1%} of OOS days")

# Check known stress periods
for label, (start, end) in [
    ("COVID (Feb-Apr 2020)",  ("2020-02-01", "2020-04-30")),
    ("2022 drawdown (Jan-Jun)", ("2022-01-01", "2022-06-30")),
]:
    period = regime_history.loc[start:end]
    if period.empty:
        print(f"  {label}: no data (outside OOS range)")
        continue
    high_pct = (period["regime"] == 1).mean()
    print(f"  {label}: {high_pct:.1%} of days in high-vol regime")
```

---

## Cell 13 [CODE]

```python
# ── Plot regime history ───────────────────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
fig.suptitle("HMM 2-State Volatility Regime Detection", fontsize=13, fontweight="bold")

# Portfolio return with regime shading
port_oos = portfolio_returns.reindex(regime_history.index)
ax1.plot(port_oos.index, port_oos.values * 100, color="#145c72", linewidth=0.8,
         label="Portfolio daily return (%)")
ax1.fill_between(regime_history.index,
                 port_oos.values * 100,
                 0,
                 where=(regime_history["regime"].values == 1),
                 alpha=0.2, color="#a33b3b", label="High-vol regime")
ax1.axhline(0, color="gray", linewidth=0.5)
ax1.set_ylabel("Daily Return (%)")
ax1.legend(fontsize=9, loc="upper right")
ax1.grid(True, alpha=0.2)

# P(high-vol) over time
ax2.fill_between(regime_history.index,
                 regime_history["prob_high_vol"].values * 100,
                 0,
                 alpha=0.4, color="#a33b3b")
ax2.plot(regime_history.index,
         regime_history["prob_high_vol"].values * 100,
         color="#a33b3b", linewidth=1.2, label="P(High-Vol Regime) %")
ax2.axhline(50, color="gray", linewidth=0.8, linestyle="--")
ax2.set_ylabel("P(High-Vol) %")
ax2.set_ylim(0, 100)
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "hmm_regime_history.png", dpi=150, bbox_inches="tight")
plt.show()
print("Chart saved.")
```

---

## Cell 14 [MARKDOWN]

### Regime-conditioned VaR validation

Compute historical VaR separately for each regime using the OOS regime labels. High-vol VaR should be substantially larger than low-vol VaR — this is the key evidence that regime conditioning improves risk estimation.

---

## Cell 15 [CODE]

```python
# ── Regime-conditioned VaR ────────────────────────────────────────────────────
CONFIDENCE = 0.99

port_with_regime = pd.concat([
    portfolio_returns.rename("ret"),
    regime_history["regime"],
], axis=1).dropna()

for state, label in [(0, "Low-Vol"), (1, "High-Vol")]:
    r_state = port_with_regime.loc[port_with_regime["regime"] == state, "ret"]
    if len(r_state) < 30:
        print(f"{label}: insufficient data ({len(r_state)} obs)")
        continue
    var_pct = float(np.percentile(r_state.values, (1 - CONFIDENCE) * 100))
    ann_vol  = r_state.std() * np.sqrt(252)
    print(f"{label} regime:")
    print(f"  Obs:     {len(r_state):4d} days ({len(r_state)/len(port_with_regime):.1%})")
    print(f"  Ann vol: {ann_vol:.2%}")
    print(f"  VaR 99% (1-day): {abs(var_pct):.2%}")
```

---

## Cell 16 [CODE]

```python
# ── Export artifacts ──────────────────────────────────────────────────────────

# 1. Regime history (for local app: regime-conditioned VaR + dashboard chart)
regime_history.to_parquet(OUTPUT_DIR / "regime_history.parquet")

# 2. HMM parameters (for reproducibility reference only)
# Fit one final model on all data for params; walk-forward labels are the authoritative output
final_model = GaussianHMM(n_components=N_STATES, covariance_type="full",
                           n_iter=N_ITER, random_state=SEED)
final_model.fit(X_scaled)
final_states, _ = canonical_labels(final_model, final_model.predict(X_scaled))
frac_high_final  = float((final_states == 1).mean())

hmm_params = {
    "n_states":          N_STATES,
    "n_features":        X_scaled.shape[1],
    "feature_names":     list(features.columns),
    "rolling_window":    WINDOW,
    "min_train_days":    MIN_TRAIN,
    "refit_freq_days":   REFIT_FREQ,
    "n_iter":            N_ITER,
    "seed":              SEED,
    "fitted_at":         str(pd.Timestamp.now().date()),
    "oos_obs":           len(regime_history),
    "frac_high_vol_oos": round(frac_high, 3),
    "note": ("Walk-forward OOS labels in regime_history.parquet are "
             "the authoritative output. hmm_params.json is for reference only."),
}

with open(OUTPUT_DIR / "hmm_params.json", "w") as f:
    json.dump(hmm_params, f, indent=2)

print("✅ Exported:")
print(f"  regime_history.parquet  ({len(regime_history)} rows)")
print(f"  hmm_params.json")
print(f"\nCurrent regime (latest OOS date): "
      f"{'High-Vol' if regime_history['regime'].iloc[-1]==1 else 'Low-Vol'}")
```
