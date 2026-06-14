import numpy as np, pandas as pd
from src.portfolio import frontier as fr

def _inputs(seed=0):
    rng = np.random.default_rng(seed)
    R = pd.DataFrame(rng.normal(0.0005, 0.01, (500, 4)), columns=list("ABCD"))
    return R.mean().to_numpy() * 252, np.cov(R.T) * 252

def test_min_variance_weights_sum_to_one():
    _, cov = _inputs()
    w = fr.min_variance(cov, long_only=True)
    assert abs(w.sum() - 1) < 1e-6
    assert (w >= -1e-9).all()

def test_frontier_risk_monotone_nondecreasing():
    mu, cov = _inputs()
    f = fr.efficient_frontier(mu, cov, n_points=15, long_only=True)
    assert (np.diff(f["risk"]) >= -1e-9).all()      # clamp guarantees monotonicity
    assert f["risk"][-1] >= f["risk"][0]

def test_frontier_returns_increase():
    mu, cov = _inputs()
    f = fr.efficient_frontier(mu, cov, n_points=15, long_only=True)
    assert f["ret"][-1] > f["ret"][0]

def test_tangency_weights_sum_to_one():
    mu, cov = _inputs()
    w = fr.tangency(mu, cov, rf=0.0, long_only=True)
    assert abs(w.sum() - 1) < 1e-6
