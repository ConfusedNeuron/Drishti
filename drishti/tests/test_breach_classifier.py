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
