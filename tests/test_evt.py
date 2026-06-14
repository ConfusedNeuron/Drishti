import numpy as np, pandas as pd, pytest
from src.risk import evt

def test_evt_var_exceeds_threshold_quantile():
    r = pd.Series(np.random.default_rng(0).standard_t(4, 5000) * 0.01)
    v99 = evt.evt_var(r, q=0.99, threshold_q=0.90)
    v95 = evt.evt_var(r, q=0.95, threshold_q=0.90)
    assert v99 > v95 > 0          # losses as positive magnitudes

def test_evt_es_ge_var():
    r = pd.Series(np.random.default_rng(1).standard_t(4, 5000) * 0.01)
    assert evt.evt_es(r, q=0.99, threshold_q=0.90) >= evt.evt_var(r, q=0.99, threshold_q=0.90)

def test_evt_var_raises_when_q_below_threshold():
    r = pd.Series(np.random.default_rng(2).standard_t(4, 2000) * 0.01)
    with pytest.raises(ValueError):
        evt.evt_var(r, q=0.90, threshold_q=0.95)

def test_evt_degenerate_loss_tail_returns_nan_no_crash():
    r = pd.Series(np.linspace(0.001, 0.05, 500))   # all positive returns -> empty loss tail
    assert np.isnan(evt.evt_var(r, q=0.99, threshold_q=0.95))   # must NOT raise
