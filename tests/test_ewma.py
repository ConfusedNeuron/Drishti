import numpy as np, pandas as pd
from src.risk import ewma

def test_ewma_vol_length_and_nonnegative():
    r = pd.Series(np.random.default_rng(0).normal(0, 0.01, 500))
    v = ewma.ewma_vol(r, lam=0.94)
    assert len(v) == len(r)
    assert (v >= 0).all()
    assert v.iloc[-1] > 0

def test_ewma_vol_reacts_to_shock():
    r = pd.Series([0.0] * 100 + [0.10] + [0.0] * 10)   # one big shock at index 100
    v = ewma.ewma_vol(r, lam=0.94)
    assert v.iloc[101] > v.iloc[99]                    # shock enters variance the next day

def test_ewma_cov_is_symmetric_psd():
    df = pd.DataFrame(np.random.default_rng(1).normal(0, 0.01, (400, 3)), columns=list("ABC"))
    cov = ewma.ewma_cov(df, lam=0.94)
    assert cov.shape == (3, 3)
    assert np.allclose(cov, cov.T)
    assert (np.linalg.eigvalsh(cov) > -1e-10).all()
