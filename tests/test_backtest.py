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


def test_christoffersen_pi_denominator_is_transition_pairs():
    # v = [0,1,0,1,1,0,1,0,1,0,1,0,0,1,0,0,0,0]
    # n00=4, n01=6, n10=6, n11=1 → n_pairs=17 (len-1)
    # correct pi = 7/17 ≈ 0.4118  → p_value ≈ 0.0503 → PASS (> 0.05)
    # buggy   pi = 7/18 ≈ 0.3889  → p_value ≈ 0.0492 → FAIL (< 0.05)
    v = np.array([0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0])
    r = _christoffersen_test(v)
    # With the correct denominator (n_pairs = len(v)-1 = 17) the test should PASS
    assert r.pass_, (
        f"pi must be divided by n_pairs (len(v)-1=17), not len(v)=18; "
        f"correct pi≈0.4118 → p≈0.0503 (pass), buggy pi≈0.3889 → p≈0.0492 (fail). "
        f"Got p_value={r.p_value:.4f}"
    )


def test_clustering_narrative_gated_on_significance():
    # Series with one pair of consecutive violations (pi11=0.33 > pi01=0.04)
    # but only 3 total violations in 50 obs → LR statistic is small → test passes.
    # When the independence test passes, the finding must NOT say "cluster".
    v = np.zeros(50, dtype=int)
    v[10] = 1
    v[11] = 1   # one consecutive pair
    v[30] = 1   # one isolated violation
    r = _christoffersen_test(v)
    assert r.pass_, f"expected independence test to pass, got p_value={r.p_value:.4f}"
    assert "cluster" not in r.finding.lower(), (
        f"clustering narrative must be gated on test failure (pass_=False); "
        f"got finding='{r.finding}' with pass_={r.pass_}"
    )
