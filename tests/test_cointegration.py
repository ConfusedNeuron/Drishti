import numpy as np, pandas as pd
from src.research import cointegration as ci

def _cointegrated(n=600, seed=0):
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.normal(0, 1, n))           # I(1)
    y = x + rng.normal(0, 0.5, n)                # y - x is stationary
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    return pd.DataFrame({"X": x, "Y": y}, index=idx)

def test_johansen_detects_one_relation():
    out = ci.johansen_test(_cointegrated(), det_order=0, k_ar_diff=1)
    assert out["rank"] >= 1
    assert "trace_stat" in out and "crit_95" in out

def test_fit_vecm_returns_forecast():
    fc = ci.fit_vecm(_cointegrated(), k_ar_diff=1, coint_rank=1, steps=3)
    assert fc.shape == (3, 2)
    assert list(fc.columns) == ["X", "Y"]
