"""Tests for IC and Granger. Validates the fix for cross-sectional IC mis-specification."""
import numpy as np
import pandas as pd
import pytest
from src.research.ic import time_series_ic, _bh_correction


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
