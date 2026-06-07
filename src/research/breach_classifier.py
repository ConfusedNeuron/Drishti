"""
XGBoost VaR breach classifier.

Pure functions for feature construction, model loading, and inference.
Training is handled by scripts/train_breach_classifier.py.

Design decisions (from design-choices.md):
- SMOTE oversampling of breach days (rare ~1% tail events).
- Pre-trained model loaded from data/cache/models/breach_classifier.pkl.
- Risk levels: Low < 0.10, Elevated 0.10–0.25, High > 0.25.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import pandas as pd

from src.models import BreachPrediction

log = logging.getLogger(__name__)

# Thresholds for risk_level labeling
_THRESH_LOW = 0.10
_THRESH_HIGH = 0.25

# Macro Bloomberg ticker short-names used as feature column names
_MACRO_COLS = ["usdinr_ret", "indiavix_ret", "gind10yr_ret"]


def build_breach_features(
    portfolio_returns: pd.Series,
    regime_history: pd.DataFrame,
    factor_returns: pd.DataFrame,
    macro_returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Construct the feature matrix for breach classification.

    Returns a DataFrame with target column 'breach' (1 if return < −VaR percent).
    VaR percent is estimated from historical quantile of the same return series
    so the target is self-consistent with the app's historical VaR.
    """
    r = portfolio_returns.copy().sort_index()

    # Past-only breach threshold: the 1% (99% VaR) quantile of returns strictly
    # BEFORE day t. shift(1) excludes the current day; expanding(min_periods=252)
    # means no label until a year of history exists. A full-sample quantile here
    # would leak the future return distribution into every label.
    var_thresh = r.shift(1).expanding(min_periods=252).quantile(0.01)

    feats = pd.DataFrame(index=r.index)

    # Rolling volatility features
    feats["rolling_vol_5"]  = r.rolling(5).std()
    feats["rolling_vol_21"] = r.rolling(21).std()
    feats["rolling_vol_63"] = r.rolling(63).std()

    # Lagged return features
    feats["ret_lag1"] = r.shift(1)
    feats["ret_lag2"] = r.shift(2)
    feats["ret_lag5"] = r.shift(5)

    # Regime features — align on intersection dates
    if not regime_history.empty and "regime" in regime_history.columns:
        rh = regime_history.reindex(r.index).ffill()
        feats["regime"] = rh["regime"].fillna(0).astype(float)
        if "prob_high_vol" in rh.columns:
            feats["prob_high_vol"] = rh["prob_high_vol"].fillna(0.5)
        else:
            feats["prob_high_vol"] = 0.5
    else:
        feats["regime"] = 0.0
        feats["prob_high_vol"] = 0.5

    # Macro return features — use Bloomberg ticker short names mapped to column names
    # Expected columns in macro_returns: "usdinr_ret", "indiavix_ret", "gind10yr_ret"
    for col in _MACRO_COLS:
        if not macro_returns.empty and col in macro_returns.columns:
            feats[col] = macro_returns[col].reindex(r.index).ffill()
        else:
            feats[col] = 0.0

    # Commodity factor lag features — 1-day lagged returns for Brent, Gold, Copper.
    # shift(1) avoids look-ahead; these are meaningful predictors for Indian equity
    # tail risk given commodity-sensitive sectors in NIFTY 200.
    _COMMODITY_COLS = {"brent": "brent_lag1", "gold": "gold_lag1", "copper": "copper_lag1"}
    for src_col, feat_col in _COMMODITY_COLS.items():
        if not factor_returns.empty and src_col in factor_returns.columns:
            feats[feat_col] = factor_returns[src_col].reindex(r.index).ffill().shift(1)
        else:
            feats[feat_col] = 0.0

    # Target: 1 if next-day return falls below the historical VaR threshold.
    # shift(-1) ensures the model predicts tomorrow's breach from today's features,
    # avoiding same-day self-reference (look-ahead bias).
    # NaN comparison (NaN < threshold) evaluates False, so we must propagate NaN
    # explicitly before astype — the dropna() below then drops the last row.
    next_ret = r.shift(-1)
    breach = next_ret < var_thresh
    feats["breach"] = breach.where(next_ret.notna() & var_thresh.notna()).astype("Int8")

    return feats.dropna()


def load_classifier(model_path: Path) -> object | None:
    """Load pickled XGBoost classifier. Returns None if file missing or corrupt."""
    if not model_path.exists():
        return None
    try:
        with open(model_path, "rb") as fh:
            return pickle.load(fh)
    except Exception as exc:
        log.warning("Failed to load breach classifier from %s: %s", model_path, exc)
        return None


def predict_breach(model: object, features_today: pd.Series) -> BreachPrediction:
    """
    Run the loaded model on today's feature vector.

    features_today: a pd.Series with feature names matching training columns
    (all columns in build_breach_features output except 'breach').
    """
    try:
        # Reshape to (1, n_features) for sklearn-compatible .predict_proba()
        x = features_today.values.reshape(1, -1)
        prob = float(model.predict_proba(x)[0, 1])

        if prob < _THRESH_LOW:
            risk_level = "Low"
        elif prob < _THRESH_HIGH:
            risk_level = "Elevated"
        else:
            risk_level = "High"

        # Native XGBoost feature importances (gain-based)
        importances: list[dict] = []
        if hasattr(model, "feature_importances_"):
            feat_names = list(features_today.index)
            imps = model.feature_importances_
            pairs = sorted(
                zip(feat_names, imps), key=lambda t: t[1], reverse=True
            )
            importances = [
                {"feature": f, "importance": round(float(v), 4)}
                for f, v in pairs[:8]
            ]

        return BreachPrediction(
            breach_probability=round(prob, 4),
            risk_level=risk_level,
            top_features=importances,
            model_available=True,
            note="",
        )
    except Exception as exc:
        log.warning("Breach prediction failed: %s", exc)
        return BreachPrediction(
            breach_probability=0.0,
            risk_level="Low",
            top_features=[],
            model_available=False,
            note=f"Prediction error: {exc}",
        )
