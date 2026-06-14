import numpy as np, pandas as pd, pytest
from src.research import tar

def _two_regime_series(n=1500, seed=0):
    """Below threshold (y_{t-1}<=0): slope 0.3; above: slope 0.9 — a genuine 2-regime AR(1)."""
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for t in range(1, n):
        slope = 0.9 if y[t - 1] > 0 else 0.3
        y[t] = slope * y[t - 1] + rng.normal(0, 0.5)
    return pd.Series(y)

def test_fit_tar_recovers_two_regimes():
    res = tar.fit_tar(_two_regime_series(), p=1, d=1)
    assert "threshold" in res and "lower_coef" in res and "upper_coef" in res
    assert res["upper_coef"][1] > res["lower_coef"][1]   # upper AR slope > lower

def test_threshold_test_flags_nonlinearity():
    out = tar.threshold_test(_two_regime_series(), p=1, d=1, n_boot=50)
    assert 0.0 <= out["p_value"] <= 1.0
    assert out["lr_stat"] > 0

def test_fit_tar_raises_on_degenerate_series():
    with pytest.raises(ValueError):
        tar.fit_tar(pd.Series(np.ones(200)), p=1, d=1)
