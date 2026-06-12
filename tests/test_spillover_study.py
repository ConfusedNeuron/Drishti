import numpy as np
import pandas as pd
import pytest
from scripts.build_spillover_study import build_study


def _make_synthetic_frame(n_cols: int = 5, n_rows: int = 600, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    return pd.DataFrame(rng.normal(0, 0.01, (n_rows, n_cols)),
                        index=idx, columns=[f"s{i}" for i in range(n_cols)])


def test_study_artifact_schema():
    large_sectors = _make_synthetic_frame(4, 600, seed=0)
    mid_sectors = _make_synthetic_frame(3, 600, seed=1)
    factors = _make_synthetic_frame(3, 600, seed=2)
    art = build_study(large_sectors, mid_sectors, factors, train_end="2022-12-31")
    assert set(art) >= {"as_of", "train_end", "panels", "rolling"}
    assert set(art["panels"]) == {"large", "mid", "combined"}
    for panel_name, p in art["panels"].items():
        assert {"total_spillover", "net_spillover", "in_sample", "out_of_sample"} <= set(p), \
            f"Panel '{panel_name}' missing keys"


def test_study_handles_missing_oos(monkeypatch):
    # If all data is before train_end, OOS should be gracefully absent (None or empty)
    large_sectors = _make_synthetic_frame(4, 400, seed=3)
    art = build_study(large_sectors, pd.DataFrame(), pd.DataFrame(), train_end="2025-12-31")
    # Should not crash even with empty mid/factors
    assert "panels" in art
