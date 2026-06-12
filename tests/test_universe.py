import json
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from src.research.universe import build_size_buckets, sector_composites, load_universe


def test_size_buckets_from_manifest():
    manifest = {
        "BIG IN Equity":  {"first_seen": "20000630", "last_seen": "20261231", "indices": ["NSE100 Index"]},
        "MID IN Equity":  {"first_seen": "20180630", "last_seen": "20261231", "indices": ["NSEMD150 Index"]},
        "BOTH IN Equity": {"first_seen": "20100630", "last_seen": "20261231",
                           "indices": ["NSE100 Index", "NSEMD150 Index"]},
    }
    u = build_size_buckets(manifest)
    assert "BIG IN Equity" in u["large"]
    assert "MID IN Equity" in u["mid"]
    # NSE100 membership wins (large bucket takes precedence)
    assert "BOTH IN Equity" in u["large"]
    assert "BOTH IN Equity" not in u["mid"]


def test_sector_composites_equal_weight():
    idx = pd.date_range("2023-01-01", periods=50, freq="B")
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "A IN Equity": rng.normal(0, 0.01, 50),
        "B IN Equity": rng.normal(0, 0.01, 50),
        "C IN Equity": rng.normal(0, 0.01, 50),
    }, index=idx)
    sectors = {"A IN Equity": "Energy", "B IN Equity": "Energy", "C IN Equity": "Banks"}
    composites = sector_composites(df, sectors)
    # Energy composite should equal mean of A and B
    expected_energy = df[["A IN Equity", "B IN Equity"]].mean(axis=1)
    pd.testing.assert_series_equal(
        composites["Energy"].dropna(), expected_energy.dropna(),
        check_names=False, rtol=1e-10
    )


def test_load_universe_returns_empty_when_no_manifest(tmp_path, monkeypatch):
    import src.research.universe as u_mod
    monkeypatch.setattr(u_mod, "V2_META", tmp_path)
    result = u_mod.load_universe()
    assert result == {}
