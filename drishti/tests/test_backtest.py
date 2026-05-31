"""Tests for Kupiec and Christoffersen backtest."""
import numpy as np
import pytest
from src.risk.backtest import _kupiec_test, _christoffersen_test, run_var_backtest


def test_kupiec_pass_at_1pct():
    """Exactly 1% violation rate should pass at 99% confidence."""
    n = 1000
    v = 10   # exactly 1%
    result = _kupiec_test(v, n, confidence=0.99)
    assert result.pass_, f"Expected pass, got p={result.p_value:.4f}"
    assert result.violation_rate == pytest.approx(0.01)


def test_kupiec_fail_at_3pct():
    """3% violation rate should fail at 99% confidence."""
    result = _kupiec_test(30, 1000, confidence=0.99)
    assert not result.pass_, f"Expected fail, got p={result.p_value:.4f}"


def test_christoffersen_pass_independent():
    """Violations evenly spread → independence test passes."""
    v = np.zeros(500, dtype=int)
    v[::50] = 1   # one violation every 50 days — independent
    result = _christoffersen_test(v)
    assert result.pass_, f"Expected pass for independent violations, p={result.p_value:.4f}"


def test_christoffersen_fail_clustered():
    """Violations in consecutive blocks → independence test fails."""
    v = np.zeros(1000, dtype=int)
    # Create blocks of 5 consecutive violations every 200 days
    for start in range(0, 1000, 200):
        v[start:start+5] = 1
    result = _christoffersen_test(v)
    assert not result.pass_, f"Expected fail for clustered violations, p={result.p_value:.4f}"
    assert "cluster" in result.finding.lower()


def test_full_backtest(simple_returns):
    result = run_var_backtest(simple_returns, portfolio_value=1_000_000,
                              confidence=0.99, rolling_window=100)
    assert result.obs > 0
    assert result.violations >= 0
    assert result.verdict  # non-empty


def test_backtest_insufficient_data(simple_returns):
    short = simple_returns[:20]
    with pytest.raises(ValueError, match="Need at least"):
        run_var_backtest(short, portfolio_value=1_000_000)
