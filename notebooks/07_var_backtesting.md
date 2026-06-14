# Notebook 07 — VaR Model Backtesting
> Run in: **Local machine (Jupyter) or BQuant**
> Inputs: `equities_returns.parquet` (from Notebook 01) OR Bloomberg cache parquet files (from `scripts/pull_bloomberg_data.py`)
> Output artifact: `var_backtest_results.json`

---


# Drishti — Portfolio Risk Analytics
## IIM Calcutta PGDBA | Financial Risk Management | Sem 3

**Project overview**

Drishti computes Value at Risk using three methods and then validates whether those models are statistically reliable. VaR is only useful if it is calibrated correctly — a 99% VaR model that is breached 3% of the time is dangerously misleading.

This notebook performs the formal statistical validation of the VaR model — the component that distinguishes Drishti from basic portfolio analytics tools. The Kupiec and Christoffersen tests come directly from regulatory VaR backtesting frameworks (Basel II/III) and are standard in any professional risk management system.

---


## Notebook 07 — VaR Model Backtesting

**What this notebook does:**

Backtests the historical simulation VaR model on the demo portfolio using two complementary statistical tests:

**Test 1: Kupiec (1995) — Unconditional Coverage Test**
Tests whether the observed violation rate equals the stated confidence level.
- H₀: violation rate = 1 − confidence (e.g., 1% for 99% VaR)
- Test statistic: likelihood ratio, χ²(1) distributed
- Failure mode: model is systematically too optimistic OR too conservative

**Test 2: Christoffersen (1998) — Independence Test**
Tests whether violations are independent (randomly distributed through time) or cluster.
- H₀: violations occur independently
- Failure mode: violations cluster → GARCH volatility clustering not captured by historical VaR
- This is the more interesting test: a model can pass Kupiec but fail Christoffersen if VaR is correctly calibrated on average but wrong during crises

**Backtest procedure:**
1. For each day t after an initial 252-day burn-in, compute the 99% historical VaR using only the past 252 days of returns.
2. Record whether the actual return on day t exceeded the VaR threshold (violation = 1).
3. Run both tests on the violation sequence.

**Output:** `var_backtest_results.json` — test statistics, p-values, violation dates, verdict.

---


```python
# ── Imports ────────────────────────────────────────────────────────────────
import pandas as pd
import numpy as np
from scipy import stats
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

# Can run from BQuant (use INPUT_DIR below) or locally (use local cache path)
INPUT_DIR  = Path("/bquant/data/drishti")          # BQuant path
# INPUT_DIR = Path("data/cache/research_artifacts") # local alternative

OUTPUT_DIR = INPUT_DIR

print("Loading equity returns...")
```

---


```python
# ── Load data and build portfolio return series ───────────────────────────────
equity_returns = pd.read_parquet(INPUT_DIR / "equities_returns.parquet")

# Equal-weighted portfolio return (proxy; replace with actual weights if available)
# In production: load weights from the Zerodha/CSV portfolio import
portfolio_returns = equity_returns.mean(axis=1)
portfolio_returns.name = "portfolio"
portfolio_returns = portfolio_returns.dropna()

print(f"Portfolio returns: {len(portfolio_returns)} trading days")
print(f"  Date range: {portfolio_returns.index[0].date()} to {portfolio_returns.index[-1].date()}")
print(f"  Ann. vol: {portfolio_returns.std() * 252**0.5:.2%}")
print(f"  Ann. return: {portfolio_returns.mean() * 252:.2%}")
```

---


### Rolling VaR computation

For each day t in the test window:
- Use the 252-day return history ending at t-1 (no lookahead — data through t-1 only)
- Take the 1st percentile of this 252-day distribution as the 1-day 99% VaR estimate
- Compare to the actual return on day t

A **violation** occurs when the actual return is worse than the VaR estimate.

---


```python
# ── Rolling historical VaR ────────────────────────────────────────────────────
CONFIDENCE   = 0.99
ALPHA        = 1 - CONFIDENCE     # = 0.01
ROLLING_WINDOW = 252              # 1 year of trading days

r = portfolio_returns.values
n = len(r)

var_estimates  = []   # VaR estimate at each test date
violations_arr = []   # 1 if actual return < VaR estimate, else 0
test_dates     = []
actual_returns = []

for t in range(ROLLING_WINDOW, n):
    window = r[t - ROLLING_WINDOW: t]
    var_threshold = np.percentile(window, ALPHA * 100)  # negative number

    actual = r[t]
    is_violation = 1 if actual < var_threshold else 0

    var_estimates.append(var_threshold)
    violations_arr.append(is_violation)
    actual_returns.append(actual)
    test_dates.append(portfolio_returns.index[t])

violations_arr = np.array(violations_arr)
n_test    = len(violations_arr)
n_viol    = int(violations_arr.sum())
viol_rate = n_viol / n_test

print(f"Backtest window: {test_dates[0].date()} to {test_dates[-1].date()}")
print(f"Observations: {n_test}")
print(f"Violations: {n_viol} observed vs {n_test * ALPHA:.1f} expected")
print(f"Violation rate: {viol_rate:.3%} vs expected {ALPHA:.2%}")
```

---


### Test 1: Kupiec Likelihood Ratio Test

The Kupiec test computes a likelihood ratio statistic comparing:
- The likelihood of observing x violations under H₀ (rate = α)
- The likelihood under H₁ (rate = x/n, the observed rate)

LR = −2 × ln[(1−α)^(n−x) × α^x] + 2 × ln[(1−x/n)^(n−x) × (x/n)^x]

LR ~ χ²(1) under H₀. Reject H₀ if LR > 3.841 (5% critical value).

---


```python
# ── Kupiec unconditional coverage test ───────────────────────────────────────

def kupiec_test(n_viol: int, n_obs: int, confidence: float) -> dict:
    p = 1 - confidence
    v = n_viol
    n = n_obs

    if v == 0:
        lr = -2 * n * np.log(1 - p)
    elif v == n:
        lr = -2 * n * np.log(p)
    else:
        lr = -2 * (
            (n - v) * np.log(1 - p) + v * np.log(p) -
            (n - v) * np.log(1 - v/n) - v * np.log(v/n)
        )

    p_value = float(1 - stats.chi2.cdf(lr, df=1))

    return {
        "test":                "Kupiec (1995) — Unconditional Coverage",
        "lr_statistic":        round(float(lr), 4),
        "p_value":             round(p_value, 4),
        "critical_value_5pct": 3.841,
        "pass":                p_value > 0.05,
        "violations":          int(v),
        "expected_violations": round(n * p, 2),
        "violation_rate":      round(v / n, 4),
        "expected_rate":       p,
    }


kupiec = kupiec_test(n_viol, n_test, CONFIDENCE)
print(f"Kupiec LR statistic: {kupiec['lr_statistic']:.4f}")
print(f"p-value: {kupiec['p_value']:.4f}")
print(f"Result: {'✅ PASS' if kupiec['pass'] else '❌ FAIL'}")
print(f"Interpretation: violation rate {kupiec['violation_rate']:.3%} vs expected {kupiec['expected_rate']:.2%}")
```

---


### Test 2: Christoffersen Independence Test

The independence test examines the *serial structure* of violations. We count transitions between violation/non-violation states and estimate the Markov transition probabilities:
- π₀₁ = P(violation tomorrow | no violation today)
- π₁₁ = P(violation tomorrow | violation today)

Under independence (H₀): π₀₁ = π₁₁ (history doesn't matter).
Clustering: π₁₁ > π₀₁ (violation today → higher probability of violation tomorrow).

---


```python
# ── Christoffersen independence test ─────────────────────────────────────────

def christoffersen_test(violation_series: np.ndarray) -> dict:
    v = violation_series.astype(int)

    # Count transitions
    n00 = int(((v[:-1] == 0) & (v[1:] == 0)).sum())
    n01 = int(((v[:-1] == 0) & (v[1:] == 1)).sum())
    n10 = int(((v[:-1] == 1) & (v[1:] == 0)).sum())
    n11 = int(((v[:-1] == 1) & (v[1:] == 1)).sum())

    pi01 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0.0
    pi11 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0.0
    pi   = (n01 + n11) / len(v)

    def _log(x): return np.log(max(x, 1e-10))

    lr = -2 * (
        (n00 + n10) * _log(1 - pi) + (n01 + n11) * _log(pi) -
        n00 * _log(1 - pi01) - n01 * _log(pi01) -
        n10 * _log(1 - pi11) - n11 * _log(pi11)
    )

    p_value = float(1 - stats.chi2.cdf(lr, df=1))
    clustering = pi11 > pi01

    return {
        "test":         "Christoffersen (1998) — Independence",
        "lr_statistic": round(float(lr), 4),
        "p_value":      round(p_value, 4),
        "critical_value_5pct": 3.841,
        "pass":         p_value > 0.05,
        "pi01":         round(pi01, 4),
        "pi11":         round(pi11, 4),
        "clustering":   bool(clustering),
        "finding": (
            "Violations cluster — model underestimates volatility persistence. "
            "Consider GARCH-conditioned VaR or regime-conditioned VaR."
            if clustering else
            "Violations appear independent — no evidence of clustering."
        ),
        "transition_counts": {
            "n00": n00, "n01": n01, "n10": n10, "n11": n11,
        },
    }


christo = christoffersen_test(violations_arr)
print(f"Christoffersen LR statistic: {christo['lr_statistic']:.4f}")
print(f"p-value: {christo['p_value']:.4f}")
print(f"π₀₁ = {christo['pi01']:.4f}  (P(viol | no viol yesterday))")
print(f"π₁₁ = {christo['pi11']:.4f}  (P(viol | viol yesterday))")
print(f"Result: {'✅ PASS' if christo['pass'] else '❌ FAIL'}")
print(f"Finding: {christo['finding']}")
```

---


```python
# ── Verdict ────────────────────────────────────────────────────────────────────
if kupiec["pass"] and christo["pass"]:
    verdict = "Model passes both coverage and independence tests. Historical VaR at 99% is well-calibrated."
elif kupiec["pass"] and not christo["pass"]:
    verdict = ("Unconditional coverage acceptable; violations cluster. "
               "Historical VaR understates volatility persistence. "
               "Recommend GARCH-FHS or regime-conditioned VaR.")
elif not kupiec["pass"] and christo["pass"]:
    verdict = "VaR systematically miscalibrated — recalibrate confidence level or switch to longer lookback window."
else:
    verdict = "Model fails both tests. Switch to GARCH-FHS or regime-conditioned VaR."

print(f"\nVerdict: {verdict}")
```

---


```python
# ── Visualise violations ──────────────────────────────────────────────────────
import matplotlib.pyplot as plt

test_dates_dt = pd.DatetimeIndex(test_dates)
port_test     = pd.Series(actual_returns, index=test_dates_dt)
var_test      = pd.Series(var_estimates,  index=test_dates_dt)
viol_dates    = test_dates_dt[violations_arr == 1]

fig, ax = plt.subplots(figsize=(14, 5))
ax.plot(port_test.index, port_test.values * 100,
        color="#5d6d7e", linewidth=0.7, label="Daily Return (%)")
ax.plot(var_test.index,  var_test.values * 100,
        color="#a33b3b", linewidth=1.2, linestyle="--", label="99% VaR threshold (%)")
ax.scatter(viol_dates,
           port_test.loc[viol_dates].values * 100,
           color="#a33b3b", s=25, zorder=5, label=f"Violations ({n_viol})")

ax.axhline(0, color="gray", linewidth=0.5)
ax.set_ylabel("Return / VaR (%)")
ax.set_title(f"VaR Backtest — 99% Historical VaR | Kupiec: {'Pass' if kupiec['pass'] else 'Fail'} | "
             f"Christoffersen: {'Pass' if christo['pass'] else 'Fail'}",
             fontsize=11)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.2)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "var_backtest.png", dpi=150, bbox_inches="tight")
plt.show()
print("Chart saved.")
```

---


```python
# ── Export results ────────────────────────────────────────────────────────────
output = {
    "confidence":     CONFIDENCE,
    "rolling_window": ROLLING_WINDOW,
    "n_obs":          n_test,
    "violations":     n_viol,
    "violation_rate": round(viol_rate, 4),
    "expected_rate":  ALPHA,
    "kupiec":         kupiec,
    "christoffersen": christo,
    "verdict":        verdict,
    "violation_dates": [str(d.date()) for d in viol_dates],
}

output_path = OUTPUT_DIR / "var_backtest_results.json"
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)

print(f"✅ Exported backtest results to {output_path}")
print(f"\nSummary:")
print(f"  Violations: {n_viol} / {n_test} ({viol_rate:.2%} vs expected {ALPHA:.2%})")
print(f"  Kupiec:         {'PASS' if kupiec['pass'] else 'FAIL'} (p={kupiec['p_value']:.4f})")
print(f"  Christoffersen: {'PASS' if christo['pass'] else 'FAIL'} (p={christo['p_value']:.4f})")
```
