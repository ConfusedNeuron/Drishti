import numpy as np, pandas as pd
from src.research import liquidity

def test_amihud_higher_for_thinner_volume():
    n = 300
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    rng = np.random.default_rng(0)
    ret = pd.Series(rng.normal(0, 0.02, n), index=idx)
    px = pd.Series(100.0, index=idx)
    thick = pd.Series(1e7, index=idx)
    thin = pd.Series(1e4, index=idx)
    illiq_thin = liquidity.amihud(ret, px, thin)
    illiq_thick = liquidity.amihud(ret, px, thick)
    assert illiq_thin > illiq_thick > 0

def test_amihud_nan_on_zero_volume():
    n = 50
    idx = pd.date_range("2021-01-01", periods=n, freq="B")
    ret = pd.Series(np.random.default_rng(1).normal(0, 0.02, n), index=idx)
    px = pd.Series(100.0, index=idx)
    vol = pd.Series(0.0, index=idx)
    assert np.isnan(liquidity.amihud(ret, px, vol))
