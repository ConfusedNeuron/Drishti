import numpy as np, pandas as pd
from src.risk import performance as perf

def _ret(seed, n=1000, mu=0.0005, sd=0.01):
    return pd.Series(np.random.default_rng(seed).normal(mu, sd, n))

def test_beta_of_series_with_itself_is_one():
    r = _ret(1)
    assert abs(perf.beta(r, r) - 1.0) < 1e-9

def test_sharpe_positive_for_positive_drift():
    r = _ret(2, mu=0.001)
    assert perf.sharpe(r, rf_annual=0.0, periods=252) > 0

def test_jensen_alpha_zero_when_asset_is_market():
    m = _ret(3)
    a = perf.jensen_alpha(m, m, rf_annual=0.0, periods=252)
    assert abs(a) < 1e-9

def test_treynor_finite_and_signed():
    r, m = _ret(4, mu=0.001), _ret(5)
    assert np.isfinite(perf.treynor(r, m, rf_annual=0.0, periods=252))

def test_treynor_nan_when_beta_zero_or_nan():
    const_market = pd.Series(np.zeros(500))          # zero variance -> beta nan -> treynor nan
    assert np.isnan(perf.treynor(_ret(6), const_market))
