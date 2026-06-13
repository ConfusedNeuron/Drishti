import numpy as np
import pandas as pd
from src.research.events import detect_drawdown_episodes, match_labels, episode_stats


def test_detect_finds_constructed_crash():
    idx = pd.date_range("2019-01-01", periods=600, freq="B")
    px = pd.Series(100.0, index=idx)
    px.iloc[200:230] = np.linspace(100, 72, 30)   # -28% crash
    px.iloc[230:] = np.linspace(72, 105, 370)
    eps = detect_drawdown_episodes(px, threshold=0.10)
    assert len(eps) == 1
    e = eps[0]
    assert abs(e["depth"] + 0.28) < 0.02
    assert e["peak_date"] < e["trough_date"]


def test_no_episode_below_threshold():
    idx = pd.date_range("2019-01-01", periods=300, freq="B")
    px = pd.Series(np.linspace(100, 130, 300), index=idx)
    assert detect_drawdown_episodes(px, threshold=0.10) == []


def test_episode_stats_returns_expected_keys():
    idx = pd.date_range("2020-01-01", periods=200, freq="B")
    px = pd.Series(100.0, index=idx)
    px.iloc[50:80] = np.linspace(100, 70, 30)
    px.iloc[80:] = np.linspace(70, 105, 120)
    eps = detect_drawdown_episodes(px, threshold=0.10)
    assert len(eps) >= 1
    # Build simple 2-sector DataFrame
    sector_px = pd.DataFrame({
        "Energy": px * 0.9 + np.random.default_rng(0).normal(0, 1, len(idx)),
        "Banks": px * 1.1 + np.random.default_rng(1).normal(0, 1, len(idx)),
    }, index=idx)
    stats = episode_stats(eps[0], sector_px)
    assert {"sector_falls", "recovery_days", "first_to_recover", "positive_through"} <= set(stats)
