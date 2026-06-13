import numpy as np
import pandas as pd
from src.risk.returns import filter_min_history, portfolio_returns


def _series(start, periods, seed):
    idx = pd.date_range(start, periods=periods, freq="B")
    return pd.Series(np.random.default_rng(seed).normal(0, 0.01, periods), index=idx)


def test_young_listing_does_not_truncate_matrix():
    old = _series("2018-01-01", 2000, 0)
    young = _series("2025-01-01", 200, 1)   # recent IPO — only 200 days
    prices = pd.DataFrame({
        "OLD": (1 + old).cumprod() * 100,
        "YOUNG": (1 + young).cumprod() * 50,
    })
    kept = filter_min_history(prices, min_days=756)
    assert "YOUNG" not in kept.columns
    assert "OLD" in kept.columns
    # OLD's history must be fully preserved, not truncated to YOUNG's start
    assert kept["OLD"].dropna().index.min() == prices["OLD"].dropna().index.min()


def test_all_kept_when_all_meet_threshold():
    prices = pd.DataFrame({
        "A": pd.Series(range(1000), index=pd.date_range("2021-01-01", periods=1000, freq="B"), dtype=float),
        "B": pd.Series(range(1000), index=pd.date_range("2021-01-01", periods=1000, freq="B"), dtype=float),
    })
    kept = filter_min_history(prices, min_days=756)
    assert list(kept.columns) == ["A", "B"]


def test_weight_renormalization_after_drop():
    df = pd.DataFrame({"A": [0.01, 0.02], "B": [0.0, 0.01]},
                      index=pd.date_range("2024-01-01", periods=2, freq="B"))
    port = portfolio_returns(df, {"A": 0.5, "B": 0.25, "MISSING": 0.25})
    # common = ["A","B"]; w after renorm = {"A": 0.5/0.75, "B": 0.25/0.75} = {2/3, 1/3}
    assert abs(port.iloc[0] - (0.01 * (2/3) + 0.0 * (1/3))) < 1e-12
