import pandas as pd
from src.research import series_io

def test_load_index_prices_reads_px_last(tmp_path, monkeypatch):
    d = tmp_path / "cache" / "bloomberg_v2" / "indices"
    d.mkdir(parents=True)
    idx = pd.date_range("2020-01-01", periods=5, freq="B")
    pd.DataFrame({"PX_LAST": [100, 101, 102, 103, 104]}, index=idx).to_parquet(d / "NIFTY_Index.parquet")
    monkeypatch.setattr(series_io, "V2", tmp_path / "cache" / "bloomberg_v2")
    px = series_io.load_index_prices(["NIFTY Index"])
    assert list(px.columns) == ["NIFTY Index"]
    assert px["NIFTY Index"].iloc[-1] == 104

def test_load_close_skips_missing_and_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(series_io, "V2", tmp_path / "cache" / "bloomberg_v2")
    assert series_io.load_index_prices(["DOESNOTEXIST Index"]).empty

def test_load_ohlc_returns_four_fields(tmp_path, monkeypatch):
    d = tmp_path / "cache" / "bloomberg_v2" / "ohlc" / "indices"
    d.mkdir(parents=True)
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    pd.DataFrame({"PX_OPEN":[1,2,3],"PX_HIGH":[2,3,4],"PX_LOW":[0.5,1.5,2.5],"PX_LAST":[1.5,2.5,3.5]},
                 index=idx).to_parquet(d / "NIFTY_Index.parquet")
    monkeypatch.setattr(series_io, "V2", tmp_path / "cache" / "bloomberg_v2")
    ohlc = series_io.load_ohlc("NIFTY Index", "indices")
    assert set(["open","high","low","close"]).issubset(ohlc.columns)
    assert ohlc["high"].iloc[-1] == 4

def test_load_ohlc_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(series_io, "V2", tmp_path / "cache" / "bloomberg_v2")
    assert series_io.load_ohlc("NIFTY Index", "indices").empty
