"""Tests for all three VaR methods."""
import numpy as np
import pytest
from src.risk.var import historical_var, parametric_var, garch_fhs_var


def test_historical_var_1d(simple_returns):
    result = historical_var(simple_returns, portfolio_value=1_000_000, confidence=0.99)
    assert result.method == "historical"
    assert result.amount > 0
    assert 0 < result.percent < 0.10   # sanity: 1-day 99% VaR < 10%


def test_historical_var_10d(simple_returns):
    result = historical_var(simple_returns, portfolio_value=1_000_000,
                            confidence=0.99, horizon_days=10)
    result_1d = historical_var(simple_returns, portfolio_value=1_000_000, confidence=0.99)
    # 10-day VaR should be larger than 1-day
    assert result.amount > result_1d.amount


def test_parametric_var(multi_asset_returns):
    w = np.array([0.5, 0.3, 0.2])
    cov = multi_asset_returns.cov().values
    result = parametric_var(w, cov, portfolio_value=1_000_000, confidence=0.99)
    assert result.method == "parametric"
    assert result.amount > 0
    assert "normal" in result.note.lower()


def test_garch_fhs_var(simple_returns):
    result = garch_fhs_var(simple_returns, portfolio_value=1_000_000, confidence=0.99)
    assert result.method == "garch_fhs"
    assert result.amount > 0
    assert result.obs > 100


def test_all_three_methods_different(simple_returns, multi_asset_returns):
    """The three VaR methods must produce different estimates."""
    from src.risk.var import all_var_methods
    w = np.array([0.4, 0.35, 0.25])
    cov = multi_asset_returns.cov().values
    port = (multi_asset_returns * w).sum(axis=1)
    results = all_var_methods(port, w, cov, 1_000_000)
    amounts = [r.amount for r in results.values()]
    # They should not all be identical
    assert not (amounts[0] == amounts[1] == amounts[2]), \
        "All three methods returned the same VaR — parametric and GARCH-FHS must differ."
