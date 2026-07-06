"""Tests for src/portfolio/frontier_studio.py — pure-function core (diagnostic only)."""
import numpy as np
import pandas as pd
import pytest

from src.portfolio import frontier_studio as fs
from src.portfolio.frontier import efficient_frontier, tangency


def _random_daily_frame(n_days=300, n_assets=4, seed=0, columns=None):
    rng = np.random.default_rng(seed)
    cols = columns or list("ABCD"[:n_assets])
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    data = rng.normal(0.0005, 0.01, (n_days, len(cols)))
    return pd.DataFrame(data, index=idx, columns=cols)


# ---------------------------------------------------------------------------
# to_monthly
# ---------------------------------------------------------------------------

def test_to_monthly_series_matches_manual_compounding():
    dates = pd.to_datetime(
        ["2021-01-04", "2021-01-05", "2021-01-06", "2021-02-01", "2021-02-02"]
    )
    values = [0.01, -0.02, 0.005, 0.03, -0.01]
    r = pd.Series(values, index=dates)

    monthly = fs.to_monthly(r)

    expected_jan = (1.01) * (0.98) * (1.005) - 1
    expected_feb = (1.03) * (0.99) - 1

    assert len(monthly) == 2
    assert monthly.iloc[0] == pytest.approx(expected_jan, abs=1e-12)
    assert monthly.iloc[1] == pytest.approx(expected_feb, abs=1e-12)


def test_to_monthly_dataframe_preserves_columns():
    dates = pd.to_datetime(
        ["2021-01-04", "2021-01-05", "2021-01-06", "2021-02-01", "2021-02-02"]
    )
    a = [0.01, -0.02, 0.005, 0.03, -0.01]
    b = [0.02, 0.01, -0.01, -0.005, 0.02]
    df = pd.DataFrame({"A": a, "B": b}, index=dates)

    monthly = fs.to_monthly(df)

    assert list(monthly.columns) == ["A", "B"]
    expected_a_jan = (1.01) * (0.98) * (1.005) - 1
    expected_b_feb = (0.995) * (1.02) - 1
    assert monthly["A"].iloc[0] == pytest.approx(expected_a_jan, abs=1e-12)
    assert monthly["B"].iloc[1] == pytest.approx(expected_b_feb, abs=1e-12)


# ---------------------------------------------------------------------------
# to_weekly_frame
# ---------------------------------------------------------------------------

def test_to_weekly_frame_preserves_columns_and_compounds():
    dates = pd.bdate_range("2021-03-01", "2021-03-05")  # Mon-Fri, single W-FRI bucket
    a = [0.01, -0.005, 0.02, 0.0, -0.01]
    b = [-0.02, 0.01, 0.005, 0.03, 0.0]
    df = pd.DataFrame({"A": a, "B": b}, index=dates)

    weekly = fs.to_weekly_frame(df)

    assert list(weekly.columns) == ["A", "B"]
    expected_a = 1
    for v in a:
        expected_a *= 1 + v
    expected_a -= 1
    expected_b = 1
    for v in b:
        expected_b *= 1 + v
    expected_b -= 1

    assert len(weekly) == 1
    assert weekly["A"].iloc[0] == pytest.approx(expected_a, abs=1e-12)
    assert weekly["B"].iloc[0] == pytest.approx(expected_b, abs=1e-12)


# ---------------------------------------------------------------------------
# estimate_inputs — validation
# ---------------------------------------------------------------------------

def test_estimate_inputs_bad_horizon_raises_with_valid_keys_listed():
    df = _random_daily_frame()
    with pytest.raises(ValueError, match="unknown horizon"):
        fs.estimate_inputs(df, "bogus")
    try:
        fs.estimate_inputs(df, "bogus")
    except ValueError as e:
        for key in fs.HORIZONS:
            assert key in str(e)


# ---------------------------------------------------------------------------
# estimate_inputs — annualization
# ---------------------------------------------------------------------------

def test_estimate_inputs_daily_annualization_matches_manual_mean():
    df = _random_daily_frame(n_days=300, n_assets=4, seed=42)
    mu, cov, symbols, meta = fs.estimate_inputs(df, "1y")

    lookback, freq = fs.HORIZONS["1y"]
    assert freq == "D"
    manual_slice = df.iloc[-lookback:]
    manual_mu = manual_slice.mean(axis=0).to_numpy() * 252

    assert symbols == list(df.columns)
    np.testing.assert_allclose(mu, manual_mu, atol=1e-9)
    assert meta["frequency"] == "D"


def test_estimate_inputs_weekly_frequency_and_scale():
    df = _random_daily_frame(n_days=300, n_assets=4, seed=7)
    mu, cov, symbols, meta = fs.estimate_inputs(df, "5y")

    lookback, freq = fs.HORIZONS["5y"]
    assert freq == "W"
    assert meta["frequency"] == "W"

    manual_slice = df.iloc[-lookback:]
    manual_weekly = fs.to_weekly_frame(manual_slice)
    manual_weekly = manual_weekly.dropna(axis=1, thresh=fs.MIN_OBS["W"])
    manual_weekly = manual_weekly.dropna()
    manual_mu = manual_weekly.mean(axis=0).to_numpy() * 52

    assert symbols == list(manual_weekly.columns)
    np.testing.assert_allclose(mu, manual_mu, atol=1e-9)


# ---------------------------------------------------------------------------
# estimate_inputs — Ledoit-Wolf shrinkage
# ---------------------------------------------------------------------------

def test_estimate_inputs_ledoit_wolf_shrinkage_applied():
    df = _random_daily_frame(n_days=300, n_assets=4, seed=1)
    mu, cov, symbols, meta = fs.estimate_inputs(df, "1y")

    assert meta["shrinkage"] is not None
    assert isinstance(meta["shrinkage"], float)
    assert 0.0 <= meta["shrinkage"] <= 1.0
    assert cov.shape == (4, 4)
    np.testing.assert_allclose(cov, cov.T, atol=1e-10)


# ---------------------------------------------------------------------------
# estimate_inputs — guards
# ---------------------------------------------------------------------------

def test_estimate_inputs_guard_too_few_columns():
    df = _random_daily_frame(n_days=300, n_assets=2, seed=2, columns=["A", "B"])
    with pytest.raises(ValueError, match="≥3 assets"):
        fs.estimate_inputs(df, "1y")


def test_estimate_inputs_guard_too_few_rows():
    # Each column individually clears MIN_OBS["D"]=60 (64 rows, 4 NaNs each) so the
    # column-drop guard does not fire, but the 4 columns' NaNs land on disjoint rows,
    # so the row-wise intersection after dropna is only 48 rows — below MIN_OBS — and
    # the row-count guard must fire instead.
    df = _random_daily_frame(n_days=64, n_assets=4, seed=3)
    df.iloc[0:4, 0] = np.nan
    df.iloc[4:8, 1] = np.nan
    df.iloc[8:12, 2] = np.nan
    df.iloc[12:16, 3] = np.nan
    assert (df.count() == 60).all()

    with pytest.raises(ValueError, match="observations"):
        fs.estimate_inputs(df, "1y")


def test_estimate_inputs_dropped_symbols_populated():
    df = _random_daily_frame(n_days=300, n_assets=4, seed=4, columns=["A", "B", "C", "D"])
    # Column E: mostly NaN — fewer than MIN_OBS["D"] (60) non-NaN observations.
    e = pd.Series(np.nan, index=df.index, name="E")
    e.iloc[:10] = 0.001
    df = pd.concat([df, e], axis=1)

    mu, cov, symbols, meta = fs.estimate_inputs(df, "1y")

    assert "E" in meta["dropped_symbols"]
    assert "E" not in symbols
    assert meta["dropped_symbols"] == sorted(meta["dropped_symbols"])


# ---------------------------------------------------------------------------
# portfolio_point
# ---------------------------------------------------------------------------

def test_portfolio_point_full_coverage():
    symbols = ["A", "B", "C"]
    mu = np.array([0.1, 0.08, 0.05])
    cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.03, 0.005], [0.0, 0.005, 0.02]])
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}

    result = fs.portfolio_point(weights, symbols, mu, cov)

    assert result["coverage"] == pytest.approx(1.0)
    assert result["vol"] > 0
    assert np.isfinite(result["ret"])


def test_portfolio_point_partial_coverage():
    symbols = ["A", "B", "C"]
    mu = np.array([0.1, 0.08, 0.05])
    cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.03, 0.005], [0.0, 0.005, 0.02]])
    weights = {"A": 0.5, "Z": 0.5}  # Z not in symbols

    result = fs.portfolio_point(weights, symbols, mu, cov)

    assert result["coverage"] == pytest.approx(0.5)
    assert result["vol"] is not None
    assert result["ret"] is not None
    assert np.isfinite(result["vol"])
    assert np.isfinite(result["ret"])


def test_portfolio_point_empty_intersection():
    symbols = ["A", "B", "C"]
    mu = np.array([0.1, 0.08, 0.05])
    cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.03, 0.005], [0.0, 0.005, 0.02]])
    weights = {"X": 0.6, "Y": 0.4}

    result = fs.portfolio_point(weights, symbols, mu, cov)

    assert result == {"vol": None, "ret": None, "coverage": 0.0}


# ---------------------------------------------------------------------------
# resampled_band
# ---------------------------------------------------------------------------

def _band_inputs(seed=0, n_days=150, n_assets=3, n_points=5):
    """Small daily return frame + a real frontier (for a ret_grid) — kept tiny so
    the n_boot=250->100 cap test doesn't take forever (each boot iter re-solves
    a full mini-frontier)."""
    returns_freq = _random_daily_frame(n_days=n_days, n_assets=n_assets, seed=seed)
    factor = 252
    values = returns_freq.values
    mu = values.mean(axis=0) * factor
    cov = np.cov(values, rowvar=False) * factor
    frontier = efficient_frontier(mu, cov, n_points=n_points, long_only=True)
    return returns_freq, frontier["ret"], factor


def test_resampled_band_deterministic_same_seed():
    returns_freq, ret_grid, factor = _band_inputs()

    band1 = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                               factor=factor, n_boot=5, seed=42)
    band2 = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                               factor=factor, n_boot=5, seed=42)

    np.testing.assert_array_equal(band1["risk_lo"], band2["risk_lo"])
    np.testing.assert_array_equal(band1["risk_hi"], band2["risk_hi"])


def test_resampled_band_different_seed_differs():
    returns_freq, ret_grid, factor = _band_inputs()

    band1 = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                               factor=factor, n_boot=5, seed=42)
    band2 = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                               factor=factor, n_boot=5, seed=7)

    lo_diff = not np.allclose(band1["risk_lo"], band2["risk_lo"], equal_nan=True)
    hi_diff = not np.allclose(band1["risk_hi"], band2["risk_hi"], equal_nan=True)
    assert lo_diff or hi_diff


def test_resampled_band_shapes_and_n_boot_echo():
    returns_freq, ret_grid, factor = _band_inputs()

    band = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                              factor=factor, n_boot=5, seed=1)

    assert len(band["risk_lo"]) == len(ret_grid)
    assert len(band["risk_hi"]) == len(ret_grid)
    assert len(band["ret"]) == len(ret_grid)
    assert band["n_boot"] == 5


def test_resampled_band_n_boot_capped_at_100():
    returns_freq, ret_grid, factor = _band_inputs()

    band = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                              factor=factor, n_boot=250, seed=1)

    assert band["n_boot"] == 100


def test_resampled_band_lo_le_hi():
    returns_freq, ret_grid, factor = _band_inputs()

    band = fs.resampled_band(returns_freq, ret_grid, rf=0.0, long_only=True,
                              factor=factor, n_boot=8, seed=3)

    lo, hi = band["risk_lo"], band["risk_hi"]
    both_finite = ~np.isnan(lo) & ~np.isnan(hi)
    assert both_finite.any()
    assert np.all(lo[both_finite] <= hi[both_finite] + 1e-9)


# ---------------------------------------------------------------------------
# risk_presets
# ---------------------------------------------------------------------------

def _frontier_and_tangency(seed=0, n_days=250, n_assets=4, n_points=15):
    df = _random_daily_frame(n_days=n_days, n_assets=n_assets, seed=seed)
    mu, cov, symbols, meta = fs.estimate_inputs(df, "1y")
    frontier = efficient_frontier(mu, cov, n_points=n_points, long_only=True)
    w_tan = tangency(mu, cov, rf=0.0, long_only=True)
    tang_vol = float(np.sqrt(w_tan @ cov @ w_tan))
    return frontier, tang_vol, symbols


def test_risk_presets_three_in_order_and_clamped():
    frontier, tang_vol, symbols = _frontier_and_tangency()

    presets = fs.risk_presets(frontier, tang_vol, symbols)

    assert len(presets) == 3
    assert [p["label"] for p in presets] == ["conservative", "balanced", "aggressive"]

    lo_r, hi_r = float(frontier["risk"].min()), float(frontier["risk"].max())
    for p in presets:
        assert lo_r - 1e-9 <= p["vol"] <= hi_r + 1e-9


def test_risk_presets_weights_sum_to_one():
    frontier, tang_vol, symbols = _frontier_and_tangency()

    presets = fs.risk_presets(frontier, tang_vol, symbols)

    for p in presets:
        total = sum(p["weights"].values())
        assert total == pytest.approx(1.0, abs=1e-3)


# ---------------------------------------------------------------------------
# weight_gap
# ---------------------------------------------------------------------------

def test_weight_gap_union_delta_and_sort_order():
    current = {"A": 0.5, "B": 0.3, "C": 0.0005}
    target = {"B": 0.3, "C": 0.0005, "D": 0.2}

    rows = fs.weight_gap(current, target)

    symbols_in_rows = {r["symbol"] for r in rows}
    assert symbols_in_rows == {"A", "B", "D"}  # C excluded — below 0.001 in both
    assert "C" not in symbols_in_rows

    by_symbol = {r["symbol"]: r for r in rows}
    assert by_symbol["A"]["current"] == pytest.approx(0.5)
    assert by_symbol["A"]["target"] == pytest.approx(0.0)
    assert by_symbol["A"]["delta"] == pytest.approx(-0.5)

    assert by_symbol["D"]["current"] == pytest.approx(0.0)
    assert by_symbol["D"]["target"] == pytest.approx(0.2)
    assert by_symbol["D"]["delta"] == pytest.approx(0.2)

    assert by_symbol["B"]["delta"] == pytest.approx(0.0)

    deltas = [abs(r["delta"]) for r in rows]
    assert deltas == sorted(deltas, reverse=True)
