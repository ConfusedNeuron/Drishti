"""Property tests for Expected Shortfall and Component VaR."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from src.risk.var import historical_var, parametric_var, garch_fhs_var
from src.risk.es import expected_shortfall
from src.risk.contribution import component_var


@pytest.fixture
def simple_returns():
    rng = np.random.default_rng(42)
    idx = pd.date_range("2018-01-01", periods=1500, freq="B")
    return pd.Series(rng.standard_normal(1500) * 0.01, index=idx)


@pytest.fixture
def multi_asset_returns():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2018-01-01", periods=1500, freq="B")
    data = {
        "A": rng.standard_normal(1500) * 0.01,
        "B": rng.standard_normal(1500) * 0.012,
        "C": rng.standard_normal(1500) * 0.008,
    }
    return pd.DataFrame(data, index=idx)


def test_es_geq_var(simple_returns):
    """ES must be >= VaR by definition (it is the mean of the tail beyond VaR)."""
    var_result = historical_var(simple_returns, 1_000_000, 0.99)
    es_result = expected_shortfall(simple_returns, 1_000_000, 0.99)
    assert es_result.amount >= var_result.amount


def test_component_var_sums_to_parametric_total(multi_asset_returns):
    """Component VaRs must sum exactly to total parametric VaR (by construction)."""
    w = np.array([0.5, 0.3, 0.2])
    cov = multi_asset_returns.cov().values
    comps = component_var(w, ["A", "B", "C"], cov, 1_000_000, 0.99)
    total = parametric_var(w, cov, 1_000_000, 0.99).amount
    assert abs(sum(c.component_var for c in comps) - total) < 1e-6 * total


def test_parametric_var_closed_form():
    """Single-asset parametric VaR equals z * sigma * portfolio_value exactly."""
    w = np.array([1.0])
    cov = np.array([[0.0004]])   # sigma = 2%/day
    res = parametric_var(w, cov, 1_000_000, 0.99)
    expected = abs(stats.norm.ppf(0.01)) * 0.02 * 1_000_000
    assert abs(res.amount - expected) < 1e-4


def test_garch_fhs_multiday_exceeds_1d(simple_returns):
    """10-day GARCH-FHS VaR must exceed the 1-day estimate."""
    r1 = garch_fhs_var(simple_returns, 1_000_000, 0.99)
    r10 = garch_fhs_var(simple_returns, 1_000_000, 0.99, horizon_days=10, n_bootstrap=2000)
    assert r10.amount > r1.amount
