"""Shared test fixtures."""
import numpy as np
import pandas as pd
import pytest

SEED = 42
N = 500   # ~2 years of daily returns


@pytest.fixture
def simple_returns() -> pd.Series:
    """Daily portfolio returns with mild GARCH clustering."""
    rng = np.random.default_rng(SEED)
    sigma2, omega, alpha, beta = 0.0001, 1e-6, 0.08, 0.88
    r = []
    for _ in range(N):
        r.append(rng.normal(0, np.sqrt(sigma2)))
        sigma2 = omega + alpha * r[-1]**2 + beta * sigma2
    return pd.Series(r, index=pd.date_range("2022-01-03", periods=N, freq="B"))


@pytest.fixture
def multi_asset_returns() -> pd.DataFrame:
    """3-asset correlated return matrix."""
    rng = np.random.default_rng(SEED)
    cov = np.array([[0.0002, 0.0001, 0.00005],
                    [0.0001, 0.0003, 0.00008],
                    [0.00005, 0.00008, 0.00015]])
    L = np.linalg.cholesky(cov)
    z = rng.standard_normal((N, 3))
    returns = z @ L.T
    return pd.DataFrame(returns, columns=["A", "B", "C"],
                        index=pd.date_range("2022-01-03", periods=N, freq="B"))
