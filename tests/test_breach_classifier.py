"""
Tests for src/research/breach_classifier.py and BreachPrediction dataclass.

No model download required — uses a tiny synthetic sklearn estimator as a
stand-in so the predict_breach() path is fully exercised.
"""
from __future__ import annotations

import pickle
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models import BreachPrediction
from src.research.breach_classifier import (
    _THRESH_HIGH,
    _THRESH_LOW,
    build_breach_features,
    load_classifier,
    predict_breach,
)


# ── Fixtures ───────────────────────────────────────────────────────────────

SEED = 42
N = 600


@pytest.fixture
def port_returns() -> pd.Series:
    rng = np.random.default_rng(SEED)
    r = rng.normal(0, 0.01, N)
    return pd.Series(r, index=pd.date_range("2021-01-04", periods=N, freq="B"))


@pytest.fixture
def regime_history(port_returns) -> pd.DataFrame:
    df = pd.DataFrame({
        "regime": np.random.default_rng(SEED).integers(0, 2, N),
        "prob_high_vol": np.random.default_rng(SEED).uniform(0, 1, N),
    }, index=port_returns.index)
    return df


@pytest.fixture
def macro_returns(port_returns) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    return pd.DataFrame({
        "usdinr_ret":   rng.normal(0, 0.003, N),
        "indiavix_ret": rng.normal(0, 0.05, N),
        "gind10yr_ret": rng.normal(0, 0.002, N),
    }, index=port_returns.index)


@pytest.fixture
def factor_returns(port_returns) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    return pd.DataFrame({
        "brent":  rng.normal(0, 0.015, N),
        "gold":   rng.normal(0, 0.008, N),
        "copper": rng.normal(0, 0.012, N),
    }, index=port_returns.index)


# ── build_breach_features ──────────────────────────────────────────────────

def test_build_features_returns_dataframe(port_returns, regime_history, factor_returns, macro_returns):
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    assert isinstance(feat, pd.DataFrame)
    assert not feat.empty


def test_feature_columns_present(port_returns, regime_history, factor_returns, macro_returns):
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    expected = [
        "rolling_vol_5", "rolling_vol_21", "rolling_vol_63",
        "ret_lag1", "ret_lag2", "ret_lag5",
        "regime", "prob_high_vol",
        "usdinr_ret", "indiavix_ret", "gind10yr_ret",
        # commodity lag features added by Fix 3
        "brent_lag1", "gold_lag1", "copper_lag1",
        "breach",
    ]
    for col in expected:
        assert col in feat.columns, f"Missing column: {col}"


def test_breach_column_binary(port_returns, regime_history, factor_returns, macro_returns):
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    assert set(feat["breach"].unique()).issubset({0, 1})


def test_breach_rate_is_near_one_percent(port_returns, regime_history, factor_returns, macro_returns):
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    breach_rate = feat["breach"].mean()
    # Expect roughly ~1% for 99th percentile tail; allow generous tolerance
    assert 0.0 < breach_rate < 0.08, f"Unexpected breach rate: {breach_rate:.3f}"


def test_no_nans_in_features(port_returns, regime_history, factor_returns, macro_returns):
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    assert not feat.isnull().any().any()


def test_empty_regime_history_handled(port_returns, factor_returns, macro_returns):
    feat = build_breach_features(
        port_returns,
        pd.DataFrame(),     # empty regime history
        factor_returns,
        macro_returns,
    )
    assert "regime" in feat.columns
    assert feat["regime"].fillna(0).equals(feat["regime"])


def test_missing_macro_cols_filled_zero(port_returns, regime_history, factor_returns):
    feat = build_breach_features(
        port_returns,
        regime_history,
        factor_returns,
        pd.DataFrame(),    # no macro data
    )
    for col in ["usdinr_ret", "indiavix_ret", "gind10yr_ret"]:
        assert col in feat.columns
        assert (feat[col] == 0).all()


def test_missing_factor_returns_commodity_lags_zero(port_returns, regime_history, macro_returns):
    """When factor_returns is empty, commodity lag columns must exist and be all zero."""
    feat = build_breach_features(
        port_returns,
        regime_history,
        pd.DataFrame(),    # no factor data
        macro_returns,
    )
    for col in ["brent_lag1", "gold_lag1", "copper_lag1"]:
        assert col in feat.columns, f"Missing commodity lag column: {col}"
        assert (feat[col] == 0).all(), f"{col} should be all-zero when factor_returns is empty"


def test_commodity_lags_are_shifted(port_returns, regime_history, macro_returns):
    """
    Commodity lag features must be 1-day lagged: feat['brent_lag1'][i] ==
    factor_returns['brent'][i-1]. Checks the shift(1) is applied correctly.
    """
    rng = np.random.default_rng(0)
    # Use a non-constant series so the shift is detectable
    factor_returns_local = pd.DataFrame({
        "brent":  rng.normal(0, 0.015, N),
        "gold":   rng.normal(0, 0.008, N),
        "copper": rng.normal(0, 0.012, N),
    }, index=port_returns.index)

    feat = build_breach_features(port_returns, regime_history, factor_returns_local, macro_returns)

    # First valid row of brent_lag1 should equal brent from the preceding date
    # feat drops NaNs, so first row has rolling windows filled — find the second
    # row in the output and verify the lag
    if len(feat) < 2:
        pytest.skip("Not enough rows to test lag shift")

    second_date = feat.index[1]
    second_loc = port_returns.index.get_loc(second_date)
    prev_date = port_returns.index[second_loc - 1]
    expected = factor_returns_local.loc[prev_date, "brent"]
    actual = feat.loc[second_date, "brent_lag1"]
    assert abs(actual - expected) < 1e-10, (
        f"brent_lag1 not correctly shifted: got {actual}, expected {expected}"
    )


# ── Look-ahead bias / next-day target property ────────────────────────────

def test_breach_target_is_next_day_return(port_returns, regime_history, factor_returns, macro_returns):
    """
    Fix 1 regression guard: breach[i] must reflect whether ret[i+1] < VaR,
    NOT ret[i]. Concretely, for every row i in the output DataFrame, the breach
    label must equal (portfolio_returns[i+1] < var_thresh[i]).

    The threshold is recomputed with the SAME past-only expanding quantile used
    inside build_breach_features (no full-sample look-ahead) so we can cross-check
    exactly per row.
    """
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)

    # Recompute the same past-only threshold used inside build_breach_features
    r = port_returns.sort_index()
    var_thresh = r.shift(1).expanding(min_periods=252).quantile(0.01)

    # For each date in the output (dropna removes last row, so feat.index ⊆ r.index[:-1])
    for date in feat.index:
        # Find the next calendar/business date in the return series
        loc = r.index.get_loc(date)
        next_loc = loc + 1
        assert next_loc < len(r), f"No next-day return for row {date}"
        thresh = var_thresh.loc[date]
        expected_breach = int(r.iloc[next_loc] < thresh)
        actual_breach = int(feat.loc[date, "breach"])
        assert actual_breach == expected_breach, (
            f"Look-ahead check failed at {date}: "
            f"breach={actual_breach}, expected (ret[i+1] < {thresh:.6f})={expected_breach} "
            f"(ret[i]={r.iloc[loc]:.6f}, ret[i+1]={r.iloc[next_loc]:.6f})"
        )


def test_breach_target_not_same_day_return(port_returns, regime_history, factor_returns, macro_returns):
    """
    Negative test: breach[i] must NOT equal (ret[i] < var_thresh[i]) for all rows
    (that would be the look-ahead-biased same-day target). For a random return
    series of length 600 there must be at least some rows where ret[i] and
    ret[i+1] differ in their breach status, so the two labelings cannot be identical.
    """
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    r = port_returns.sort_index()
    var_thresh = r.shift(1).expanding(min_periods=252).quantile(0.01)

    # same-day labeling (the OLD wrong direction) using the per-row past-only threshold
    same_day_breach = (r < var_thresh).reindex(feat.index).astype(int)

    # The two series must differ on at least one row
    assert not feat["breach"].equals(same_day_breach), (
        "breach target appears identical to same-day labeling — look-ahead bias may be present"
    )


def test_breach_threshold_is_past_only(port_returns, regime_history, factor_returns, macro_returns):
    feat = build_breach_features(port_returns, regime_history, factor_returns, macro_returns)
    r = port_returns.sort_index()
    # No labels during the 252-day expanding warm-up
    assert feat.index.min() >= r.index[252]
    # Threshold is time-varying (past-only), not a single global number
    vt = r.shift(1).expanding(min_periods=252).quantile(0.01)
    assert vt.loc[feat.index].nunique() > 1


def test_lower_confidence_yields_more_breaches(port_returns, regime_history, factor_returns, macro_returns):
    f99 = build_breach_features(port_returns, regime_history, factor_returns, macro_returns, confidence=0.99)
    f95 = build_breach_features(port_returns, regime_history, factor_returns, macro_returns, confidence=0.95)
    assert int(f95["breach"].sum()) > int(f99["breach"].sum())


# ── load_classifier ────────────────────────────────────────────────────────

def test_load_classifier_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        assert load_classifier(Path(tmp) / "no_model.pkl") is None


def test_load_classifier_corrupt_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "bad.pkl"
        p.write_bytes(b"not a pickle")
        assert load_classifier(p) is None


def test_load_classifier_valid_model():
    """Save and reload a tiny sklearn classifier via load_classifier."""
    from sklearn.dummy import DummyClassifier
    clf = DummyClassifier(strategy="most_frequent")
    clf.fit([[0, 0], [1, 1]], [0, 1])
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "model.pkl"
        with open(p, "wb") as fh:
            pickle.dump(clf, fh)
        loaded = load_classifier(p)
        assert loaded is not None
        assert hasattr(loaded, "predict_proba")


# ── predict_breach ─────────────────────────────────────────────────────────

def _make_dummy_model(proba_value: float):
    """Return a minimal sklearn-compatible estimator that always returns proba_value."""
    from sklearn.dummy import DummyClassifier
    import numpy as np

    clf = DummyClassifier(strategy="constant", constant=0)
    clf.fit([[0] * 11, [1] * 11], [0, 1])

    # Monkey-patch predict_proba to return a fixed value
    def _proba(X):
        n = len(X)
        return np.array([[1 - proba_value, proba_value]] * n)

    clf.predict_proba = _proba
    # Add dummy feature_importances_
    clf.feature_importances_ = np.array([0.1] * 11)
    return clf


@pytest.fixture
def feature_series():
    cols = [
        "rolling_vol_5", "rolling_vol_21", "rolling_vol_63",
        "ret_lag1", "ret_lag2", "ret_lag5",
        "regime", "prob_high_vol",
        "usdinr_ret", "indiavix_ret", "gind10yr_ret",
    ]
    return pd.Series([0.01] * 11, index=cols)


def test_predict_breach_returns_dataclass(feature_series):
    model = _make_dummy_model(0.05)
    result = predict_breach(model, feature_series)
    assert isinstance(result, BreachPrediction)
    assert result.model_available is True


def test_predict_breach_low_risk(feature_series):
    model = _make_dummy_model(0.05)   # below _THRESH_LOW (0.10)
    result = predict_breach(model, feature_series)
    assert result.risk_level == "Low"
    assert result.breach_probability < _THRESH_LOW


def test_predict_breach_elevated_risk(feature_series):
    model = _make_dummy_model(0.15)   # between _THRESH_LOW and _THRESH_HIGH
    result = predict_breach(model, feature_series)
    assert result.risk_level == "Elevated"


def test_predict_breach_high_risk(feature_series):
    model = _make_dummy_model(0.30)   # above _THRESH_HIGH (0.25)
    result = predict_breach(model, feature_series)
    assert result.risk_level == "High"


def test_predict_breach_top_features_populated(feature_series):
    model = _make_dummy_model(0.12)
    result = predict_breach(model, feature_series)
    assert len(result.top_features) > 0
    for item in result.top_features:
        assert "feature" in item
        assert "importance" in item


def test_predict_breach_prob_in_range(feature_series):
    for p in [0.0, 0.15, 0.50, 1.0]:
        model = _make_dummy_model(p)
        result = predict_breach(model, feature_series)
        assert 0.0 <= result.breach_probability <= 1.0


def test_predict_breach_broken_model_returns_unavailable(feature_series):
    """If predict_proba raises, predict_breach returns model_available=False."""

    class BrokenModel:
        feature_importances_ = [0.1]

        def predict_proba(self, X):
            raise RuntimeError("intentional failure")

    result = predict_breach(BrokenModel(), feature_series)
    assert result.model_available is False
    assert "intentional failure" in result.note
