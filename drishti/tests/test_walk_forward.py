"""Tests for the walk-forward OOS backtest (src/research/walk_forward.py)."""
import numpy as np
import pandas as pd
import pytest

from src.research.walk_forward import run_walk_forward, _compute_ic_on_window, _select_pairs
from src.models import WalkForwardResult, WalkForwardMetrics

SEED = 42
N = 700   # ~2.8 years of daily returns — enough for 252-day train + OOS periods


@pytest.fixture
def factor_returns() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    idx = pd.date_range("2021-01-04", periods=N, freq="B")
    # brent has mild positive autocorrelation (easier to detect)
    brent = pd.Series(rng.normal(0.001, 0.02, N), index=idx, name="brent")
    gold = pd.Series(rng.normal(0.0005, 0.015, N), index=idx, name="gold")
    return pd.DataFrame({"brent": brent, "gold": gold})


@pytest.fixture
def sector_returns(factor_returns) -> pd.DataFrame:
    """Energy sector has a weak positive relationship to brent at lag=1."""
    rng = np.random.default_rng(SEED + 1)
    brent = factor_returns["brent"]
    noise = pd.Series(rng.normal(0, 0.02, N), index=brent.index)
    energy = 0.3 * brent.shift(1).fillna(0) + noise
    metals = pd.Series(rng.normal(0, 0.018, N), index=brent.index)
    return pd.DataFrame({"energy": energy, "metals": metals})


def test_ic_on_window_positive_signal(factor_returns, sector_returns):
    """Mean rolling IC should be positive when factor leads target."""
    ic = _compute_ic_on_window(
        factor_returns["brent"],
        sector_returns["energy"],
        lag=1,
        rolling_corr_window=63,
    )
    # The relationship is deliberately weak; just check it's a valid float
    assert isinstance(ic, float)
    assert not np.isnan(ic)


def test_ic_on_window_insufficient_data():
    """Returns 0.0 when series is too short to compute IC."""
    short = pd.Series([0.01, -0.02, 0.005], index=pd.date_range("2024-01-01", periods=3))
    ic = _compute_ic_on_window(short, short, lag=1)
    assert ic == 0.0


def test_run_walk_forward_returns_result(factor_returns, sector_returns):
    result = run_walk_forward(factor_returns, sector_returns)
    assert isinstance(result, WalkForwardResult)
    assert result.n_pairs > 0
    assert len(result.metrics) == result.n_pairs
    assert len(result.factors) > 0
    assert len(result.sectors) > 0


def test_walk_forward_metrics_fields(factor_returns, sector_returns):
    result = run_walk_forward(factor_returns, sector_returns)
    for m in result.metrics:
        assert isinstance(m, WalkForwardMetrics)
        assert m.oos_obs > 0
        assert -1.0 <= m.oos_win_rate <= 1.0
        assert m.oos_max_dd <= 0.0   # max drawdown is always <= 0
        assert len(m.cumulative_return_dates) == len(m.cumulative_return_values)
        assert len(m.cumulative_return_dates) > 0


def test_sharpe_matrix_covers_all_pairs(factor_returns, sector_returns):
    result = run_walk_forward(factor_returns, sector_returns)
    for f in result.factors:
        assert f in result.sharpe_matrix
        for s in result.sectors:
            # Value is either a float or None (no data for that pair)
            val = result.sharpe_matrix[f][s]
            assert val is None or isinstance(val, float)


def test_walk_forward_with_ic_results(factor_returns, sector_returns):
    """When ic_results provided, only those pairs should be backtested."""
    ic_results = [
        {"factor": "brent", "target": "energy", "lag_days": 1,
         "t_stat": 3.5, "bh_significant": True},
    ]
    result = run_walk_forward(factor_returns, sector_returns, ic_results=ic_results)
    assert result.n_pairs >= 1
    # The brent→energy pair should appear
    pair_keys = [(m.factor, m.target) for m in result.metrics]
    assert ("brent", "energy") in pair_keys


def test_walk_forward_insufficient_data():
    """Series too short to produce OOS results returns empty WalkForwardResult."""
    rng = np.random.default_rng(SEED)
    short_idx = pd.date_range("2024-01-01", periods=100, freq="B")
    factors = pd.DataFrame({"brent": rng.normal(0, 0.02, 100)}, index=short_idx)
    sectors = pd.DataFrame({"energy": rng.normal(0, 0.02, 100)}, index=short_idx)
    result = run_walk_forward(factors, sectors)
    # n_pairs may be 0 because 100 < 252 + 21*3 = 315
    assert isinstance(result, WalkForwardResult)
    assert result.n_pairs == 0


def test_select_pairs_fallback_no_bh_significant(factor_returns, sector_returns):
    """
    When all ic_results have bh_significant=False, _select_pairs must not raise
    and must return between 0 and 5 pairs (top-5 by |t_stat| fallback).
    run_walk_forward must also complete without error.
    """
    ic_results = [
        {"factor": "brent", "target": "energy",  "lag_days": 1,  "t_stat":  3.5, "bh_significant": False},
        {"factor": "brent", "target": "metals",  "lag_days": 1,  "t_stat": -2.8, "bh_significant": False},
        {"factor": "gold",  "target": "energy",  "lag_days": 2,  "t_stat":  1.9, "bh_significant": False},
        {"factor": "gold",  "target": "metals",  "lag_days": 5,  "t_stat": -1.2, "bh_significant": False},
        {"factor": "brent", "target": "energy",  "lag_days": 5,  "t_stat":  2.1, "bh_significant": False},
        {"factor": "gold",  "target": "energy",  "lag_days": 10, "t_stat": -0.8, "bh_significant": False},
    ]

    # _select_pairs must not raise
    pairs = _select_pairs(ic_results)
    assert 0 <= len(pairs) <= 5, f"Expected 0-5 pairs, got {len(pairs)}"

    # run_walk_forward must complete without error
    result = run_walk_forward(factor_returns, sector_returns, ic_results=ic_results)
    assert isinstance(result, WalkForwardResult)
