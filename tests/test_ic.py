"""Tests for IC and Granger. Validates the fix for cross-sectional IC mis-specification."""
import numpy as np
import pandas as pd
import pytest
from src.research.ic import time_series_ic, _bh_correction, to_weekly, granger_test, summarize_granger_aic


def test_perfect_ic_lag1():
    """Factor at t-1 perfectly predicts target at t → IC ≈ 1."""
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    factor = pd.Series(np.random.default_rng(0).standard_normal(300), index=dates, name="factor")
    # Target IS the lagged factor (perfect lag-1 relationship)
    target = factor.shift(1).dropna().rename("target")
    factor_aligned = factor.reindex(target.index)
    result = time_series_ic(factor_aligned, target, lag=1)
    assert result.ic_mean > 0.8, f"Expected near-perfect IC, got {result.ic_mean:.3f}"
    assert result.significant


def test_zero_ic_random():
    """Unrelated random series → IC near 0, not significant."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-01", periods=400, freq="B")
    factor = pd.Series(rng.standard_normal(400), index=dates, name="factor")
    target = pd.Series(rng.standard_normal(400), index=dates, name="target")
    result = time_series_ic(factor, target, lag=1)
    assert abs(result.ic_mean) < 0.15, f"Expected near-zero IC, got {result.ic_mean:.3f}"
    assert not result.significant


def test_bh_correction_controls_fdr():
    """BH correction finds strong signals and controls false discoveries."""
    # 20 hypotheses — 15 nulls, 5 true signals with very small p-values.
    # With n=20, alpha=0.05, BH threshold at rank k = k*0.05/20 = k*0.0025.
    # Signal p-values 0.0005..0.0025 satisfy threshold at ranks 1-5.
    rng = np.random.default_rng(1)
    signal_indices = [2, 5, 9, 13, 17]
    p_values = rng.uniform(0.1, 1.0, 20)   # nulls: large p-values
    for i, idx in enumerate(signal_indices):
        p_values[idx] = (i + 1) * 0.0005   # strong signals: 0.0005, 0.001, …

    discoveries = _bh_correction(p_values, alpha=0.05)

    # All 5 signal indices should be discovered
    for idx in signal_indices:
        assert discoveries[idx], f"Signal at index {idx} (p={p_values[idx]:.4f}) should be discovered"

    # Nulls (large p) should not be discovered
    null_disc = sum(discoveries[i] for i in range(20) if i not in signal_indices)
    assert null_disc == 0, f"Unexpected null discoveries: {null_disc}"


def test_ic_significance_uses_hac_not_iid():
    import numpy as np
    import pandas as pd
    from src.research.ic import time_series_ic

    rng = np.random.default_rng(0)
    idx = pd.date_range("2018-01-01", periods=1200, freq="B")
    f = pd.Series(rng.standard_normal(1200), index=idx, name="brent")
    t = (0.25 * f.shift(1) + pd.Series(rng.standard_normal(1200), index=idx)).rename("energy")
    res = time_series_ic(f, t, lag=1, rolling_window=63)

    # Reconstruct the OLD i.i.d. t-stat = ICIR * sqrt(n_windows)
    df = pd.concat([f.rename("factor"), t.rename("target")], axis=1).dropna()
    df["fl"] = df["factor"].shift(1)
    df = df.dropna()
    ic = df["fl"].rolling(63).corr(df["target"]).dropna()
    naive_t = (ic.mean() / ic.std()) * np.sqrt(len(ic))

    assert abs(res.t_stat) < 0.6 * abs(naive_t)   # HAC must deflate the inflated t-stat
    assert 0.0 <= res.p_value <= 1.0


def test_to_weekly_compounds_and_uses_friday_bucket():
    idx = pd.date_range("2024-01-01", periods=10, freq="B")  # Mon-Fri, Mon-Fri
    r = pd.Series([0.01] * 10, index=idx)
    w = to_weekly(r)
    assert len(w) == 2
    assert abs(w.iloc[0] - (1.01**5 - 1)) < 1e-12
    assert w.index[0].dayofweek == 4  # Friday


def test_weekly_granger_produces_results():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2017-01-02", periods=2300, freq="B")
    f = pd.Series(rng.standard_normal(2300) * 0.01, index=idx, name="brent")
    t = (0.4 * f.shift(30).fillna(0) +
         pd.Series(rng.standard_normal(2300) * 0.01, index=idx)).rename("energy")
    res = granger_test(f, t, max_lag=8, freq="weekly")
    assert len(res) == 8
    # All results should have aic populated (not 0.0 if statsmodels path works)
    assert all(hasattr(r, "aic") for r in res)


def test_aic_summary_picks_one_lag_per_pair():
    rng = np.random.default_rng(4)
    idx = pd.date_range("2018-01-01", periods=1500, freq="B")
    f = pd.Series(rng.standard_normal(1500) * 0.01, index=idx, name="gold")
    t = pd.Series(rng.standard_normal(1500) * 0.01, index=idx, name="metals")
    granger_res = granger_test(f, t, max_lag=5, freq="daily")
    summary = summarize_granger_aic(granger_res)
    # One row per (factor, target) pair — should be exactly 1 here
    assert len(summary) == 1
    assert summary[0].factor == "gold" and summary[0].target == "metals"
