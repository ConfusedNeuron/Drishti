import numpy as np
import pandas as pd
import pytest

from src.research import spillover_lab


# ---------------------------------------------------------------------------
# build_catalog
# ---------------------------------------------------------------------------

def _empty_manifest_mocks(monkeypatch):
    monkeypatch.setattr(spillover_lab, "load_universe", lambda: {})
    monkeypatch.setattr(spillover_lab, "load_sectors", lambda: {})
    monkeypatch.setattr(spillover_lab, "build_size_buckets", lambda u: {"large": [], "mid": []})


def test_build_catalog_all_empty_when_no_cache_and_no_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(spillover_lab, "CACHE_DIR", tmp_path / "bloomberg_v2")
    _empty_manifest_mocks(monkeypatch)

    cat = spillover_lab.build_catalog()

    assert cat == {
        "equities": [], "indices": [], "commodities": [], "macro": [], "sector_composites": [],
    }


def test_build_catalog_lists_indices_commodities_macro_from_disk(tmp_path, monkeypatch):
    cache = tmp_path / "bloomberg_v2"
    (cache / "indices").mkdir(parents=True)
    (cache / "commodities").mkdir(parents=True)
    (cache / "macro").mkdir(parents=True)
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    pd.DataFrame({"PX_LAST": [1, 2, 3]}, index=idx).to_parquet(cache / "indices" / "NIFTY_Index.parquet")
    pd.DataFrame({"PX_LAST": [1, 2, 3]}, index=idx).to_parquet(cache / "commodities" / "CO1_Comdty.parquet")
    pd.DataFrame({"PX_LAST": [1, 2, 3]}, index=idx).to_parquet(cache / "macro" / "USDINR_Curncy.parquet")
    monkeypatch.setattr(spillover_lab, "CACHE_DIR", cache)
    _empty_manifest_mocks(monkeypatch)

    cat = spillover_lab.build_catalog()

    assert cat["indices"] == [{"id": "idx:NIFTY Index", "label": "NIFTY Index"}]
    assert cat["commodities"] == [{"id": "cmd:CO1 Comdty", "label": "CO1 Comdty"}]
    assert cat["macro"] == [{"id": "mac:USDINR Curncy", "label": "USDINR Curncy"}]


def test_build_catalog_equities_from_manifest_sorted_by_symbol(tmp_path, monkeypatch):
    monkeypatch.setattr(spillover_lab, "CACHE_DIR", tmp_path / "bloomberg_v2")
    manifest = {"TCS IS Equity": {}, "RELIANCE IS Equity": {}}
    monkeypatch.setattr(spillover_lab, "load_universe", lambda: manifest)
    monkeypatch.setattr(spillover_lab, "load_sectors", lambda: {
        "TCS IS Equity": "Information Technology",
        "RELIANCE IS Equity": "Energy",
    })
    monkeypatch.setattr(spillover_lab, "build_size_buckets", lambda u: {"large": [], "mid": []})

    cat = spillover_lab.build_catalog()

    assert cat["equities"] == [
        {"id": "eq:RELIANCE", "label": "RELIANCE — Energy"},
        {"id": "eq:TCS", "label": "TCS — Information Technology"},
    ]


def test_build_catalog_equity_label_unknown_sector_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(spillover_lab, "CACHE_DIR", tmp_path / "bloomberg_v2")
    monkeypatch.setattr(spillover_lab, "load_universe", lambda: {"XYZ IS Equity": {}})
    monkeypatch.setattr(spillover_lab, "load_sectors", lambda: {})
    monkeypatch.setattr(spillover_lab, "build_size_buckets", lambda u: {"large": [], "mid": []})

    cat = spillover_lab.build_catalog()

    assert cat["equities"] == [{"id": "eq:XYZ", "label": "XYZ — Unknown"}]


def test_build_catalog_sector_composite_needs_at_least_two_members(tmp_path, monkeypatch):
    monkeypatch.setattr(spillover_lab, "CACHE_DIR", tmp_path / "bloomberg_v2")
    monkeypatch.setattr(spillover_lab, "load_universe", lambda: {"dummy": {}})
    monkeypatch.setattr(spillover_lab, "load_sectors", lambda: {
        "A IS Equity": "Financials", "B IS Equity": "Financials",
        "C IS Equity": "Energy",
        "D IS Equity": "Unknown", "E IS Equity": "Unknown",
    })
    monkeypatch.setattr(spillover_lab, "build_size_buckets", lambda u: {
        "large": ["A IS Equity", "B IS Equity", "C IS Equity"],
        "mid": ["D IS Equity", "E IS Equity"],
    })

    cat = spillover_lab.build_catalog()

    # Financials has 2 members in large -> included; Energy has only 1 -> excluded;
    # Unknown sector always skipped regardless of member count.
    assert cat["sector_composites"] == [
        {"id": "sec:Financials|large", "label": "Financials (large-cap composite)"},
    ]


# ---------------------------------------------------------------------------
# resolve_series
# ---------------------------------------------------------------------------

def test_resolve_series_unknown_ids_raise_value_error_naming_all(monkeypatch):
    with pytest.raises(ValueError) as exc:
        spillover_lab.resolve_series(["bogus:FOO", "idx:DOESNOTEXIST Index"], None, None)
    msg = str(exc.value)
    assert "bogus:FOO" in msg
    assert "idx:DOESNOTEXIST Index" in msg


def test_resolve_series_equity_label_strips_prefix(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    px = pd.DataFrame({"RELIANCE IS Equity": [100, 101, 99, 102, 103]}, index=idx)
    rets = px.pct_change()

    def fake_load_v2_returns(tickers, min_days=None):
        assert tickers == ["RELIANCE IS Equity"]
        return rets

    monkeypatch.setattr(spillover_lab, "load_v2_returns", fake_load_v2_returns)

    out = spillover_lab.resolve_series(["eq:RELIANCE"], None, None)

    assert list(out.columns) == ["RELIANCE"]


def test_resolve_series_index_and_commodity_use_pct_change(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    px_idx = pd.DataFrame({"NIFTY Index": [100, 102, 101, 103, 104]}, index=idx)
    px_cmd = pd.DataFrame({"CO1 Comdty": [50, 51, 52, 51, 53]}, index=idx)

    monkeypatch.setattr(spillover_lab, "load_index_prices", lambda tickers: px_idx[tickers])
    monkeypatch.setattr(spillover_lab, "load_commodity_prices", lambda tickers: px_cmd[tickers])

    out = spillover_lab.resolve_series(["idx:NIFTY Index", "cmd:CO1 Comdty"], None, None)

    assert set(out.columns) == {"NIFTY Index", "CO1 Comdty"}
    expected = px_idx["NIFTY Index"].pct_change().to_frame("NIFTY Index").join(
        px_cmd["CO1 Comdty"].pct_change().to_frame("CO1 Comdty"), how="inner"
    ).dropna()
    pd.testing.assert_series_equal(out["NIFTY Index"], expected["NIFTY Index"], check_names=False)


def test_resolve_series_gind10yr_uses_diff_not_pct_change(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    # Constant-step ramp: diff() is constant, pct_change() is not -> distinguishes the two.
    px = pd.DataFrame({"GIND10YR Index": [6.0, 6.5, 7.0, 7.5, 8.0, 8.5]}, index=idx)

    monkeypatch.setattr(spillover_lab, "load_macro_prices", lambda tickers: px[tickers])

    out = spillover_lab.resolve_series(["mac:GIND10YR Index"], None, None)

    expected_diff = px["GIND10YR Index"].diff().dropna()
    wrong_pct_change = px["GIND10YR Index"].pct_change().dropna()

    pd.testing.assert_series_equal(out["GIND10YR Index"], expected_diff, check_names=False)
    assert not out["GIND10YR Index"].equals(wrong_pct_change)


def test_resolve_series_other_macro_uses_pct_change(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    px = pd.DataFrame({"USDINR Curncy": [80, 81, 80.5, 82, 81.5]}, index=idx)

    monkeypatch.setattr(spillover_lab, "load_macro_prices", lambda tickers: px[tickers])

    out = spillover_lab.resolve_series(["mac:USDINR Curncy"], None, None)

    expected = px["USDINR Curncy"].pct_change().dropna()
    pd.testing.assert_series_equal(out["USDINR Curncy"], expected, check_names=False)


def test_resolve_series_sector_composite(monkeypatch):
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    rng = np.random.default_rng(0)
    rets = pd.DataFrame(rng.normal(0, 0.01, (10, 2)), index=idx,
                         columns=["A IS Equity", "B IS Equity"])

    monkeypatch.setattr(spillover_lab, "load_universe", lambda: {"A IS Equity": {}, "B IS Equity": {}})
    monkeypatch.setattr(spillover_lab, "build_size_buckets",
                         lambda u: {"large": ["A IS Equity", "B IS Equity"], "mid": []})
    monkeypatch.setattr(spillover_lab, "load_sectors",
                         lambda: {"A IS Equity": "Financials", "B IS Equity": "Financials"})
    monkeypatch.setattr(spillover_lab, "load_v2_returns", lambda tickers, min_days=None: rets)

    out = spillover_lab.resolve_series(["sec:Financials|large"], None, None)

    assert list(out.columns) == ["Financials (large)"]
    expected = rets.mean(axis=1).dropna()
    pd.testing.assert_series_equal(out["Financials (large)"], expected, check_names=False)


def test_resolve_series_unknown_sector_composite_raises(monkeypatch):
    monkeypatch.setattr(spillover_lab, "load_universe", lambda: {"A IS Equity": {}})
    monkeypatch.setattr(spillover_lab, "build_size_buckets", lambda u: {"large": ["A IS Equity"], "mid": []})
    monkeypatch.setattr(spillover_lab, "load_sectors", lambda: {"A IS Equity": "Financials"})
    monkeypatch.setattr(spillover_lab, "load_v2_returns",
                         lambda tickers, min_days=None: pd.DataFrame({
                             "A IS Equity": [0.01, 0.02]
                         }, index=pd.date_range("2020-01-01", periods=2)))

    with pytest.raises(ValueError) as exc:
        spillover_lab.resolve_series(["sec:Energy|large"], None, None)
    assert "sec:Energy|large" in str(exc.value)


def test_resolve_series_aligns_on_overlap_and_drops_non_overlapping(monkeypatch):
    idx_a = pd.date_range("2020-01-01", periods=20, freq="D")
    idx_b = pd.date_range("2020-01-10", periods=20, freq="D")
    px_a = pd.Series(100 + np.arange(20, dtype=float), index=idx_a)
    px_b = pd.Series(50 + np.arange(20, dtype=float) * 0.5, index=idx_b)

    def fake_load_index_prices(tickers):
        frames = {"A Index": px_a, "B Index": px_b}
        return pd.DataFrame({t: frames[t] for t in tickers})

    monkeypatch.setattr(spillover_lab, "load_index_prices", fake_load_index_prices)

    out = spillover_lab.resolve_series(["idx:A Index", "idx:B Index"], None, None)

    ret_a = px_a.pct_change().to_frame("A Index")
    ret_b = px_b.pct_change().to_frame("B Index")
    expected_len = len(ret_a.join(ret_b, how="inner").dropna())
    assert len(out) == expected_len
    assert expected_len > 0


# ---------------------------------------------------------------------------
# run_custom_spillover — cap validation
# ---------------------------------------------------------------------------

def test_run_custom_spillover_too_few_series():
    with pytest.raises(ValueError, match=r"Need at least 3 series, got 2"):
        spillover_lab.run_custom_spillover(["a", "b"])


def test_run_custom_spillover_too_many_series():
    ids = [f"s{i}" for i in range(13)]
    with pytest.raises(ValueError, match=r"Too many series: 13 \(max 12\)"):
        spillover_lab.run_custom_spillover(ids)


def test_run_custom_spillover_horizon_out_of_range():
    with pytest.raises(ValueError, match=r"fevd_horizon 25 out of range \[5, 20\]"):
        spillover_lab.run_custom_spillover(["a", "b", "c"], fevd_horizon=25)


def test_run_custom_spillover_window_out_of_range_when_rolling():
    with pytest.raises(ValueError, match=r"window 50 out of range \[100, 500\]"):
        spillover_lab.run_custom_spillover(["a", "b", "c"], rolling=True, window=50)


def test_run_custom_spillover_step_out_of_range_when_rolling():
    with pytest.raises(ValueError, match=r"step 100 out of range \[5, 63\]"):
        spillover_lab.run_custom_spillover(["a", "b", "c"], rolling=True, step=100)


def test_run_custom_spillover_min_obs_after_alignment(monkeypatch):
    small_panel = pd.DataFrame(
        np.random.default_rng(0).normal(0, 0.01, (100, 3)),
        index=pd.date_range("2020-01-01", periods=100, freq="B"),
        columns=["a", "b", "c"],
    )
    monkeypatch.setattr(spillover_lab, "resolve_series", lambda ids, start, end: small_panel)

    with pytest.raises(ValueError, match=r"Only 100 aligned observations after date/NaN alignment; need ≥250"):
        spillover_lab.run_custom_spillover(["a", "b", "c"])


# ---------------------------------------------------------------------------
# run_custom_spillover — happy path + rolling gating
# ---------------------------------------------------------------------------

def _synthetic_panel(n_rows=400, n_cols=4, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    return pd.DataFrame(rng.normal(0, 0.01, (n_rows, n_cols)), index=idx,
                         columns=[f"s{i}" for i in range(n_cols)])


def test_run_custom_spillover_happy_path(monkeypatch):
    panel = _synthetic_panel(400, 4, seed=1)
    monkeypatch.setattr(spillover_lab, "resolve_series", lambda ids, start, end: panel)

    out = spillover_lab.run_custom_spillover(["s0", "s1", "s2", "s3"])

    assert 0 < out["total_connectedness"] < 100
    assert abs(sum(out["net_spillover"].values())) < 1e-6
    assert len(out["pairwise"]) == 4
    assert out["meta"]["n_series"] == 4
    assert out["meta"]["n_obs"] == 400
    assert out["meta"]["labels"] == list(panel.columns)
    assert out["rolling"] is None
    assert out["meta"]["dropped_note"] is None


def test_run_custom_spillover_rolling_too_short_sets_dropped_note(monkeypatch):
    panel = _synthetic_panel(310, 4, seed=2)  # < window(300) + step(21) = 321
    monkeypatch.setattr(spillover_lab, "resolve_series", lambda ids, start, end: panel)

    out = spillover_lab.run_custom_spillover(
        ["s0", "s1", "s2", "s3"], rolling=True, window=300, step=21
    )

    assert out["rolling"] is None
    assert out["meta"]["dropped_note"] is not None


def test_run_custom_spillover_rolling_long_enough_returns_series(monkeypatch):
    panel = _synthetic_panel(400, 4, seed=3)  # >= window(300) + step(21) = 321
    monkeypatch.setattr(spillover_lab, "resolve_series", lambda ids, start, end: panel)

    out = spillover_lab.run_custom_spillover(
        ["s0", "s1", "s2", "s3"], rolling=True, window=300, step=21
    )

    assert out["rolling"] is not None
    assert len(out["rolling"]["dates"]) == len(out["rolling"]["values"])
    assert len(out["rolling"]["dates"]) > 0
    assert out["meta"]["dropped_note"] is None
