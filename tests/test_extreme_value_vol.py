import numpy as np, pandas as pd, pytest
from src.risk import extreme_value_vol as ev

def _ohlc(n=300, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.01, n))
    openp = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(openp, close) * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = np.minimum(openp, close) * (1 - np.abs(rng.normal(0, 0.003, n)))
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame({"open": openp, "high": high, "low": low, "close": close}, index=idx)

def test_estimators_positive_and_finite():
    d = _ohlc()
    for f in (ev.parkinson, ev.garman_klass, ev.rogers_satchell):
        v = f(d, annualize=True)
        assert np.isfinite(v) and v > 0

def test_three_estimators_in_same_ballpark():
    d = _ohlc(seed=5)
    vals = [ev.parkinson(d), ev.garman_klass(d), ev.rogers_satchell(d)]
    assert max(vals) / min(vals) < 3.0     # same clean data -> similar magnitude

def test_higher_range_gives_higher_parkinson():
    a = _ohlc(seed=1)
    b = a.copy()
    b["high"] = b["high"] * 1.05
    b["low"] = b["low"] * 0.95
    assert ev.parkinson(b) > ev.parkinson(a)

def test_empty_frame_returns_nan():
    assert np.isnan(ev.parkinson(pd.DataFrame()))

def test_missing_column_raises():
    d = _ohlc(seed=2)[["high", "low"]]
    with pytest.raises(KeyError):
        ev.garman_klass(d)     # needs open/close
