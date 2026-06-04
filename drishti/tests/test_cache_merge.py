"""Tests for read_merged() — Bloomberg + public cache merge."""
import pandas as pd
import pytest
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq


def _write_parquet(path: Path, dates: list, values: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"PX_LAST": values}, index=pd.to_datetime(dates))
    df.index.name = "date"
    pq.write_table(pa.Table.from_pandas(df), path)


def test_read_merged_bloomberg_only(tmp_path, monkeypatch):
    import src.bloomberg.cache as c
    monkeypatch.setattr(c, "CACHE_DIR",        tmp_path / "bloomberg")
    monkeypatch.setattr(c, "PUBLIC_CACHE_DIR", tmp_path / "public")
    _write_parquet(
        tmp_path / "bloomberg" / "equities" / "TEST_IN_Equity.parquet",
        ["2024-01-01", "2024-01-02"], [100.0, 101.0]
    )
    result = c.read_merged("TEST IN Equity")
    assert result is not None
    assert len(result) == 2


def test_read_merged_appends_public(tmp_path, monkeypatch):
    import src.bloomberg.cache as c
    monkeypatch.setattr(c, "CACHE_DIR",        tmp_path / "bloomberg")
    monkeypatch.setattr(c, "PUBLIC_CACHE_DIR", tmp_path / "public")
    _write_parquet(
        tmp_path / "bloomberg" / "equities" / "TEST_IN_Equity.parquet",
        ["2024-01-01", "2024-01-02"], [100.0, 101.0]
    )
    _write_parquet(
        tmp_path / "public" / "equities" / "TEST_IN_Equity.parquet",
        ["2024-01-03", "2024-01-04"], [102.0, 103.0]
    )
    result = c.read_merged("TEST IN Equity")
    assert len(result) == 4


def test_bloomberg_wins_on_overlap(tmp_path, monkeypatch):
    import src.bloomberg.cache as c
    monkeypatch.setattr(c, "CACHE_DIR",        tmp_path / "bloomberg")
    monkeypatch.setattr(c, "PUBLIC_CACHE_DIR", tmp_path / "public")
    _write_parquet(
        tmp_path / "bloomberg" / "equities" / "TEST_IN_Equity.parquet",
        ["2024-01-02"], [101.0]
    )
    _write_parquet(
        tmp_path / "public" / "equities" / "TEST_IN_Equity.parquet",
        ["2024-01-02", "2024-01-03"], [999.0, 103.0]
    )
    result = c.read_merged("TEST IN Equity")
    assert len(result) == 2
    assert float(result.loc["2024-01-02", "PX_LAST"]) == 101.0


def test_read_merged_no_cache_returns_none(tmp_path, monkeypatch):
    import src.bloomberg.cache as c
    monkeypatch.setattr(c, "CACHE_DIR",        tmp_path / "bloomberg")
    monkeypatch.setattr(c, "PUBLIC_CACHE_DIR", tmp_path / "public")
    assert c.read_merged("NONEXISTENT IN Equity") is None
