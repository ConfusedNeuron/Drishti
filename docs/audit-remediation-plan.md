# Drishti Audit Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the verified correctness, look-ahead, and data-integrity bugs found in the 2026-06-05 code audit, each behind a regression test that currently fails.

**Architecture:** Test-first. For every bug, first write a test that encodes the *correct* behavior and watch it fail (several existing tests bake in the bug and must be rewritten), then apply the minimal fix and watch it pass. Group into 3 phases by execution order: data integrity (quick, unblocks real-data validation) → methodology correctness (the core) → safety/serving hardening.

**Tech Stack:** Python, pandas/numpy, statsmodels, scipy, xgboost, FastAPI, pytest. `PYTHONPATH=. pytest` from the repo root.

**Source of findings:** memory `project_drishti_code_audit.md`. Severity tags: 🔴 critical · 🟠 high · 🟡 medium.

---

## Phase 1 — Data integrity (quick wins, unblock real-data runs)

These bugs are invisible on synthetic data (self-consistent) and only bite on real Bloomberg data, silently dropping holdings/sectors. Fix first so methodology fixes can be validated on the real cache.

### Task 1.1 🟠 — Correct sector index tickers in `config.py`

**Files:** Modify `src/config.py:53-61` · Test `tests/test_config_tickers.py` (create)

- [ ] **Write failing test**

```python
# tests/test_config_tickers.py
from src.config import SECTOR_TICKERS

def test_sector_tickers_use_valid_bloomberg_codes():
    # NSEOILGS / NSEMETAL do not exist on Bloomberg (lessons.md); correct = NSENRG / NSEMET
    assert SECTOR_TICKERS["energy"] == "NSENRG Index"
    assert SECTOR_TICKERS["metals"] == "NSEMET Index"
    for v in SECTOR_TICKERS.values():
        assert "NSEOILGS" not in v and "NSEMETAL" not in v
```

- [ ] **Fix:** in `src/config.py` set `"energy": "NSENRG Index"`, `"metals": "NSEMET Index"`. Leave `fmcg/it/banks` (NSEFMCG/NSEIT/NSEBANK are confirmed in the cache layout). **DECISION/VERIFY:** confirm `auto`→`NSEAUTO` and `pharma`→`NSEPHRM` on the terminal before the next pull — do not assume.
- [ ] **Verify & commit:** `PYTHONPATH=. pytest tests/test_config_tickers.py -v` → PASS. `git commit -m "fix(config): correct NSENRG/NSEMET sector index codes"`

### Task 1.2 🟠 — Align `_BUILTIN_TICKERS` to real Bloomberg codes + remove the Tata Consumer mis-map

**Files:** Modify `src/bloomberg/tickers.py:15-64` · Test `tests/test_ticker_registry.py` (create)

- [ ] **Write failing test**

```python
# tests/test_ticker_registry.py
from src.bloomberg.tickers import registry

CORRECT = {
    "HDFCBANK": "HDFCB IN Equity", "INFY": "INFO IN Equity",
    "ICICIBANK": "ICICIBC IN Equity", "KOTAKBANK": "KMB IN Equity",
    "BAJFINANCE": "BAF IN Equity", "HINDUNILVR": "HUVR IN Equity",
    "HCLTECH": "HCLT IN Equity", "WIPRO": "WPRO IN Equity",
    "NESTLEIND": "NEST IN Equity", "ASIANPAINT": "APNT IN Equity",
    "TATAMOTORS": "TTMT IN Equity", "HINDALCO": "HNDL IN Equity",
    "POWERGRID": "PWGR IN Equity", "TATASTEEL": "TATA IN Equity",
    "TITAN": "TTAN IN Equity", "MARUTI": "MSIL IN Equity",
}

def test_builtin_tickers_match_bloomberg_codes():
    for nse, bbg in CORRECT.items():
        assert registry.resolve(nse) == bbg

def test_tataconsum_not_priced_as_tata_motors():
    assert registry.resolve("TATACONSUM") != "TTMT IN Equity"
```

- [ ] **Fix:** update the 16 entries above to the lessons.md codes. For `TATACONSUM`: its real code is unverified — **remove the entry** so `resolve()` falls back to `"TATACONSUM IN Equity"` (a safe cache-miss) rather than mispricing as Tata Motors; add a `# TODO verify on terminal` note.
- [ ] **Verify & commit:** `pytest tests/test_ticker_registry.py -v` → PASS. `git commit -m "fix(tickers): use Bloomberg codes in builtin map; drop TATACONSUM→TTMT mis-map"`

### Task 1.3 🟡 — Regenerate synthetic cache + add a no-silent-drop guard

**Files:** Test `tests/test_ticker_registry.py` (extend) · run `scripts/generate_synthetic_cache.py`

- [ ] **Write failing test:** after Task 1.2, synthetic files still use old names. Add a test that every sample-portfolio holding resolves to a ticker with a cache file.

```python
def test_sample_holdings_have_cache_after_resolve(tmp_path, monkeypatch):
    from src.portfolio.importer import load_sample_portfolio
    from src.bloomberg.cache import get_prices
    from src.config import default_dates
    snap = load_sample_portfolio()
    start, end = default_dates()
    missing = [h.symbol for h in snap.modeled_holdings
               if get_prices(h.bbg_ticker, start, end, "PX_LAST") is None]
    assert missing == [], f"silent cache miss for {missing}"
```

- [ ] **Fix:** `PYTHONPATH=. python scripts/generate_synthetic_cache.py` to rewrite the synthetic cache under the corrected ticker names (the generator reads `_BUILTIN_TICKERS`/`SECTOR_TICKERS`, so Tasks 1.1–1.2 make it self-consistent again).
- [ ] **Verify & commit:** test PASS. `git commit -m "test(tickers): guard against silent holding drops on resolve"`

### Task 1.4 🟡 — Centralize `_category()` routing (single source of truth)

**Files:** Modify `src/bloomberg/cache.py` (export `category(ticker)`), `scripts/pull_drishti_data.py`, `scripts/pull_public_data.py` to import it.

- [ ] **Write failing test:** `tests/test_cache_merge.py` add `test_macro_tickers_route_to_macro` asserting `category("GIND10YR Index") == "macro"` and `category("INVIXN Index") == "macro"` and `category("NSEBANK Index") == "indices"`.
- [ ] **Fix:** move the routing logic into one `category()` in `cache.py` (macro tickers `GIND10YR`/`INVIXN` checked *before* the generic index rule); delete the two private copies in the scripts and import the shared one.
- [ ] **Verify & commit:** `pytest tests/test_cache_merge.py -v` → PASS. `git commit -m "refactor(cache): single category() router shared by scripts"`

---

## Phase 2 — Methodology correctness (the core)

### Task 2.1 🔴 — Fix IC significance for overlapping rolling windows (HAC / Newey-West)

**Why:** `ic.py:55-60` computes `t = ICIR·√n` on a 63-day *rolling* (overlapping) correlation series, treating ~MA(62)-dependent values as i.i.d. → t-stats inflated ≈ √63. This invalidates every "significant" flag and the entire BH-FDR claim.

**Files:** Modify `src/research/ic.py:24-72` · Test `tests/test_ic.py` (extend)

- [ ] **Write failing test**

```python
# tests/test_ic.py
import numpy as np, pandas as pd
from src.research.ic import time_series_ic

def test_ic_uses_hac_not_naive_sqrt_n():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2018-01-01", periods=1000, freq="B")
    f = pd.Series(rng.standard_normal(1000), index=idx, name="brent")
    t = (0.3 * f.shift(1) + rng.standard_normal(1000)).rename("energy")
    res = time_series_ic(f, t, lag=1, rolling_window=63)
    # naive overlapping t-stat (the OLD, wrong number):
    naive_t = res.icir * np.sqrt(res.__dict__.get("_n", 0) or 1)  # informational
    # HAC t must be materially smaller in magnitude than ICIR*sqrt(n)
    assert abs(res.t_stat) < abs(res.icir) * np.sqrt(900)
    assert 0.0 <= res.p_value <= 1.0
```

- [ ] **Fix:** replace the t-stat/p-value block in `time_series_ic` with a HAC mean test (maxlags = `rolling_window`, the overlap horizon). `statsmodels` is already a dependency.

```python
import statsmodels.api as sm
...
ic_clean = ic_series.dropna().values
n = len(ic_clean)
ic_mean = float(ic_clean.mean())
ic_std  = float(ic_clean.std(ddof=1))
icir    = ic_mean / ic_std if ic_std > 0 else 0.0
if n > rolling_window + 2 and ic_std > 0:
    ols = sm.OLS(ic_clean, np.ones(n)).fit(cov_type="HAC",
                                           cov_kwds={"maxlags": rolling_window})
    t_stat  = float(ols.tvalues[0])
    p_value = float(ols.pvalues[0])
else:
    t_stat, p_value = 0.0, 1.0
significant = p_value < 0.05
```

Keep `bh_significant` (BH is now applied to *valid* p-values, so it controls FDR). Add a one-line note to `design-choices.md` recording the HAC correction. **Optional alternative** to flag: non-overlapping windows instead of HAC (simpler, throws away data) — HAC is recommended because it preserves the rolling-IC chart.
- [ ] **Verify & commit:** `pytest tests/test_ic.py -v` → PASS. `git commit -m "fix(ic): HAC (Newey-West) significance for overlapping rolling IC"`

### Task 2.2 🔴 — Remove full-sample look-ahead in the breach target threshold

**Why:** `breach_classifier.py:49` defines the breach label against `np.percentile(r, 1)` over the *entire* series → future distribution leaks into every label. The existing tests recompute the same global threshold, so they pass while the leak stands — they must be rewritten.

**Files:** Modify `src/research/breach_classifier.py:46-101` · Modify `tests/test_breach_classifier.py`

- [ ] **Rewrite the leaky tests** so they assert a *past-only* threshold and that warm-up rows carry no label:

```python
def test_breach_threshold_is_past_only_expanding():
    # build a return series whose vol regime shifts; the early threshold must
    # differ from the late threshold (a single global number would be identical)
    ...
    feats = build_breach_features(port_ret, regime_hist, factors, macro)
    assert feats.index.min() > port_ret.index[251]   # first 252 rows have no label
```

- [ ] **Fix:** use a shifted expanding 1% quantile (the VaR you could actually have known at `t`):

```python
# Past-only breach threshold: 1% quantile of returns strictly before day t.
var_thresh = r.shift(1).expanding(min_periods=252).quantile(0.01)
...
next_ret = r.shift(-1)
breach = (next_ret < var_thresh)
feats["breach"] = breach.where(next_ret.notna() & var_thresh.notna()).astype("Int8")
return feats.dropna()    # drops the 252-row warm-up and the final shift(-1) row
```

- [ ] **Verify & commit:** `pytest tests/test_breach_classifier.py -v` → PASS. `git commit -m "fix(breach): past-only expanding VaR threshold (remove label look-ahead)"`

### Task 2.3 🟠 — Replace SMOTE with `scale_pos_weight`; drop the eval-set leak and deprecated arg

**Depends on 2.2** (don't tune resampling on a contaminated target).

**Files:** Modify `scripts/train_breach_classifier.py:98-143` · Test `tests/test_breach_classifier.py` (extend, optional smoke)

- [ ] **Fix:** delete the SMOTE block; compute `scale_pos_weight` from the (already temporal) train split; remove `use_label_encoder` (removed in xgboost ≥2.0); stop passing the test set as `eval_set` (carve a tail validation slice if early stopping is wanted, else drop it).

```python
n_breach = int(y_train.sum()); n_ok = len(y_train) - n_breach
spw = n_ok / max(n_breach, 1)
model = xgb.XGBClassifier(
    n_estimators=300, max_depth=4, learning_rate=0.05,
    eval_metric="aucpr", scale_pos_weight=spw,
    random_state=42, n_jobs=-1,
)
model.fit(X_train, y_train, verbose=False)   # no eval_set=test
```

Update `requirements.txt` (remove `imbalanced-learn` if unused elsewhere) and the SMOTE notes in `design-choices.md` / `CLAUDE.md`.
- [ ] **Verify & commit:** training runs end-to-end on synthetic cache; `git commit -m "fix(breach): scale_pos_weight over SMOTE; drop eval-set leak + deprecated arg"`

### Task 2.4 🟠 — Fix Diebold-Yilmaz `net_spillover` scale asymmetry

**Why:** `diebold_yilmaz.py:107-110` divides `to_spillover` by `k` but not `from_spillover`, so `net = to − from` mixes scales and the net transmitter/receiver labels are wrong.

**Files:** Modify `src/research/diebold_yilmaz.py:110` · Test `tests/` (create `test_diebold_yilmaz.py`)

- [ ] **Write failing test:** by construction in canonical D-Y, net spillovers sum to ~0.

```python
def test_net_spillovers_sum_to_zero():
    import numpy as np, pandas as pd
    rng = np.random.default_rng(1)
    df = pd.DataFrame(rng.standard_normal((400, 4)),
                      columns=list("abcd"),
                      index=pd.date_range("2020-01-01", periods=400, freq="B"))
    tbl = compute_spillover(df)
    assert abs(sum(tbl.net_spillover.values())) < 1e-6
```

- [ ] **Fix:** divide `from_spillover` by `k` as well:

```python
from_spillover = {names[i]: float(np.sum(theta[i, :]) - theta[i, i]) / k * 100
                  for i in range(k)}
```

- [ ] **Verify & commit:** test PASS. `git commit -m "fix(diebold-yilmaz): /k normalize from-spillover so net sums to zero"`

### Task 2.5 🟡 — Remap `prob_high_vol` to the canonical HMM state

**Why:** `hmm.py:124` reads raw posterior column 1, which disagrees with the relabeled `regime` whenever the raw ordering is inverted.

**Files:** Modify `src/research/hmm.py:117-125` · Test `tests/` (create `test_hmm.py`)

- [ ] **Write failing test:** on the labeled history, high-vol days must carry higher `prob_high_vol`.

```python
def test_prob_high_vol_matches_regime():
    out = walk_forward_hmm(port_ret, vix)       # build a real-ish series in fixture
    hi = out[out.regime == 1]["prob_high_vol"].mean()
    lo = out[out.regime == 0]["prob_high_vol"].mean()
    assert hi > lo
```

- [ ] **Fix:** map the probability column through the same vol-mean ordering used for labels.

```python
order = np.argsort(model.means_[:, 0])     # order[-1] = raw idx of high-vol state
high_raw = int(order[-1])
...
"prob_high_vol": float(oos_probs[i, high_raw]),
```

(Also note in `design-choices.md` that OOS decoding uses batch `predict()`/Viterbi; a stricter causal/filtered decode is future work.)
- [ ] **Verify & commit:** test PASS. `git commit -m "fix(hmm): remap prob_high_vol to canonical high-vol state"`

### Task 2.6 🟡 — Fix DCC-GARCH cross-series date alignment

**Why:** `dcc_garch.py:90-95` trims standardized residuals positionally (`[-min_len:]`) across independently-fit series → misaligned dates when GARCH drops different leading samples.

**Files:** Modify `src/research/dcc_garch.py:18-31, 77-95` · Test `tests/test_dcc_garch.py` (create)

- [ ] **Write failing test:** two perfectly-correlated series with *different* leading-NaN lengths must still return correlation ≈ 1 and a date-aligned index.

```python
def test_dcc_aligns_on_dates_not_positions():
    idx = pd.date_range("2019-01-01", periods=600, freq="B")
    base = pd.Series(np.random.default_rng(2).standard_normal(600), index=idx)
    a = base.copy(); b = base.copy()
    a.iloc[:20] = np.nan                       # different leading NaNs
    out = fit_dcc_garch(pd.DataFrame({"a": a, "b": b}))
    assert out["correlations"].index.is_monotonic_increasing
    assert out["correlations"].mean().iloc[0] > 0.9
```

- [ ] **Fix:** `_fit_garch11` returns the date-indexed `res.std_resid.dropna()` Series; in `fit_dcc_garch`, inner-join residuals on dates before building `Z`:

```python
std_resids = {col: _fit_garch11(returns_df[col].dropna())[0] for col in returns_df.columns}
Z_df = pd.concat(std_resids, axis=1).dropna()      # date-aligned intersection
Z, common_idx, col_names = Z_df.values, Z_df.index, list(Z_df.columns)
```

- [ ] **Verify & commit:** test PASS. `git commit -m "fix(dcc): align standardized residuals on dates, not positions"`

### Task 2.7 🟠 — Walk-forward OOS signal **[DECISION REQUIRED — do not auto-implement]**

**Why:** `walk_forward.py:90` applies a static train-IC sign to *contemporaneous* sector returns; `lag` never enters the trade and the rule collapses to long/flat buy-the-sector. Two options:

- **Option A (recommended, changes results):** make the OOS position time-varying from the realized lagged factor so the lead-lag is actually traded:

```python
oos = df.iloc[t:oos_end]
f_lag = df["factor"].shift(lag).reindex(oos.index)
expected = np.sign(ic_est) * np.sign(f_lag.values)   # +1 expect up
position = (expected > 0).astype(float)              # long-only
oos_returns.extend((oos["target"].values * position).tolist())
```

- **Option B (minimal, keeps rule):** leave the rule but add honesty metrics to `WalkForwardMetrics`: `frac_long` (fraction of OOS days positioned long) and `benchmark_sharpe` (buy-and-hold the sector). If `frac_long ≈ 1`, the report itself shows the signal is inert.

- [ ] **Get user sign-off on A vs B**, then write the test (A: assert P&L differs across `lag` values for a constructed lead-lag series; B: assert `frac_long` and `benchmark_sharpe` populate) → implement → commit.

---

## Phase 3 — Safety & serving hardening

### Task 3.1 🟠 — Unify + harden the advice safety filter

**Why:** the MCP word-boundary filter leaks advice ("position", "exit", "go long", "accumulate", "trim", "rotate", "liquidate") and over-blocks quant terms ("short", "trade"); `/api/copilot/ask` uses a *second, divergent* substring filter.

**Files:** Create `src/copilot/safety.py` · Modify `risk_mcp/tools.py`, `src/dashboard/routes/copilot.py` to import it · Test `tests/test_safety_filter.py` (create)

- [ ] **Write failing test:** a BLOCK list and a PASS list.

```python
BLOCK = ["should I buy HDFC", "go long reliance", "is this a good entry",
         "should I exit energy", "accumulate ITC", "trim my position",
         "rotate into bonds", "liquidate the portfolio", "recommend a stock"]
PASS  = ["what is the short-term VaR", "trade-weighted INR impact",
         "explain my shortfall risk", "show component VaR of my holdings"]

def test_filter(): 
    from src.copilot.safety import is_advice
    for p in BLOCK: assert is_advice(p), p
    for p in PASS:  assert not is_advice(p), p
```

- [ ] **Fix:** one word-boundary regex over an expanded token+phrase set (`buy|sell|invest|recommend|purchase|long|exit|entry|accumulate|liquidate|reallocate|rotate|trim|overweight|underweight|position|allocate|rebalance` plus phrases `should i|good (entry|buy|time)`), dropping bare `short`/`trade`. Import `is_advice` in both call sites; delete the substring filter in `copilot.py`.
- [ ] **Verify & commit:** test PASS. `git commit -m "fix(safety): unified word-boundary advice filter; close bypasses, drop false positives"`

### Task 3.2 🟡 — Stop blocking the event loop; sanitize NaN/Inf in JSON

**Files:** Modify `src/dashboard/routes/copilot.py`, `routes/research.py` (news refresh), `routes/risk.py`

- [ ] **Async:** wrap the synchronous heavy calls (GARCH-FHS, FinBERT scoring, IC study) in `await asyncio.to_thread(...)` inside the async handlers.
- [ ] **JSON:** add a small `clean_json(obj)` helper mapping non-finite floats → `None`, apply before returning dicts that can contain NaN (`risk.py` vol, `research.py` `pairwise.to_dict()`); test with an all-zero portfolio that previously produced NaN.
- [ ] **Verify & commit:** `pytest -v`; `git commit -m "fix(api): offload blocking work to threads; null out non-finite JSON"`

### Task 3.3 🟡 — Christoffersen transition-count denominator

**Files:** Modify `src/risk/backtest.py:110` · Test `tests/test_backtest.py` (extend)

- [ ] **Fix:** `pi = (n01 + n11) / (n00 + n01 + n10 + n11)` (transition pairs = N−1, not N); gate the `clustering` narrative on `not pass_`.
- [ ] **Verify & commit:** `pytest tests/test_backtest.py -v`; `git commit -m "fix(backtest): Christoffersen pi uses transition-pair denominator"`

---

## Done criteria

- [ ] `PYTHONPATH=. pytest tests/ -v` green, with **new** regression tests for 2.1, 2.2, 2.4, 2.5, 2.6 that fail on the pre-fix code.
- [ ] On the **real** Bloomberg cache, the sample portfolio loads with **zero** silent drops and energy/metals sectors populate the research tabs.
- [ ] `design-choices.md` updated: IC→HAC, breach→expanding threshold + scale_pos_weight, HMM decode note. Move the four resolved `REVISIT` items to `CONFIRMED`.
- [ ] One commit per task; no `xfail`/skips left behind.

## Sequencing notes

- 2.2 **before** 2.3 (clean target before choosing the imbalance handler).
- Phase 1 is independent and safe to land first; it unblocks validating Phase 2 on real data.
- 2.7 is the only task needing a methodology decision before code.
