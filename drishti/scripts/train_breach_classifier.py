"""
Train XGBoost VaR breach classifier and save to data/cache/models/breach_classifier.pkl.

Usage:
    PYTHONPATH=. python scripts/train_breach_classifier.py

Requires: xgboost, imbalanced-learn
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import default_dates, DATA_DIR
from src.bloomberg.cache import get_prices
from src.risk.returns import load_factor_series, load_sector_returns, portfolio_returns
from src.portfolio.importer import load_sample_portfolio
from src.risk.returns import build_return_matrix
from src.research.breach_classifier import build_breach_features
from src.research.hmm import walk_forward_hmm

MODEL_PATH = DATA_DIR / "cache" / "models" / "breach_classifier.pkl"


def main() -> None:
    print("=" * 60)
    print("Drishti — XGBoost VaR Breach Classifier Training")
    print("=" * 60)

    start, end = default_dates()
    snap = load_sample_portfolio()
    print(f"\nPortfolio: {snap.portfolio_id} ({len(snap.modeled_holdings)} holdings)")
    print(f"Date range: {start} → {end}\n")

    # Build return matrix
    returns_df, missing = build_return_matrix(snap, start, end)
    if returns_df.empty:
        print("ERROR: No cached price data. Run scripts/pull_drishti_data.py or generate_synthetic_cache.py first.")
        sys.exit(1)
    if missing:
        print(f"Missing symbols (skipped): {missing}")

    port_ret = portfolio_returns(returns_df, snap.weights)
    print(f"Portfolio return series: {len(port_ret)} observations")

    # Regime history
    vix_df = load_factor_series(["indiavix"], start, end)
    vix_series = vix_df["indiavix"] if not vix_df.empty and "indiavix" in vix_df.columns else None
    print("Fitting HMM walk-forward regimes…")
    try:
        regime_hist = walk_forward_hmm(port_ret, vix_series)
    except Exception as e:
        print(f"HMM failed ({e}), proceeding without regime features.")
        regime_hist = pd.DataFrame()

    # Macro returns
    macro_raw = load_factor_series(["usdinr", "indiavix", "gsec10y"], start, end)
    macro_renamed = macro_raw.rename(columns={
        "usdinr":   "usdinr_ret",
        "indiavix": "indiavix_ret",
        "gsec10y":  "gind10yr_ret",
    })

    factor_returns = load_factor_series(["brent", "gold", "copper"], start, end)

    print("Building feature matrix…")
    feat_df = build_breach_features(port_ret, regime_hist, factor_returns, macro_renamed)
    print(f"Feature matrix shape: {feat_df.shape}")

    feature_cols = [c for c in feat_df.columns if c != "breach"]
    X = feat_df[feature_cols].values
    y = feat_df["breach"].values

    # Split FIRST on time order (80/20) — before SMOTE to prevent synthetic
    # minority samples leaking across the boundary and inflating test metrics.
    split = int(len(X) * 0.8)
    X_train_raw, X_test = X[:split], X[split:]
    y_train_raw, y_test = y[:split], y[split:]

    # Class distribution before SMOTE (checked on training set only)
    n_breach = int(y_train_raw.sum())
    n_ok = len(y_train_raw) - n_breach
    print(f"\nClass distribution before SMOTE (train set):")
    print(f"  Normal (0): {n_ok}  ({n_ok/len(y_train_raw)*100:.1f}%)")
    print(f"  Breach (1): {n_breach}  ({n_breach/len(y_train_raw)*100:.1f}%)")

    if n_breach < 5:
        print("ERROR: Fewer than 5 breach days in training set — cannot train. Check data range or VaR threshold.")
        sys.exit(1)

    # SMOTE oversampling applied only to the training set
    try:
        from imblearn.over_sampling import SMOTE
        # k_neighbors must be < n_minority; cap at min(5, n_breach-1)
        k = min(5, int(y_train_raw.sum()) - 1)
        sm = SMOTE(random_state=42, k_neighbors=k)
        X_train, y_train = sm.fit_resample(X_train_raw, y_train_raw)
        n_breach_res = int(y_train.sum())
        n_ok_res = len(y_train) - n_breach_res
        print(f"\nClass distribution after SMOTE (train set):")
        print(f"  Normal (0): {n_ok_res}  ({n_ok_res/len(y_train)*100:.1f}%)")
        print(f"  Breach (1): {n_breach_res}  ({n_breach_res/len(y_train)*100:.1f}%)")
    except ImportError:
        print("WARNING: imbalanced-learn not installed; skipping SMOTE. pip install imbalanced-learn")
        X_train, y_train = X_train_raw, y_train_raw

    print(f"\nTraining XGBoost (n_train={len(X_train)}, n_test={len(X_test)})…")

    try:
        import xgboost as xgb
    except ImportError:
        print("ERROR: xgboost not installed. pip install xgboost")
        sys.exit(1)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        eval_metric="aucpr",
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # Evaluation: AUC-PR
    from sklearn.metrics import average_precision_score, roc_auc_score
    y_prob = model.predict_proba(X_test)[:, 1]
    auc_pr = average_precision_score(y_test, y_prob)
    auc_roc = roc_auc_score(y_test, y_prob)
    print(f"\nTest AUC-PR  : {auc_pr:.4f}")
    print(f"Test AUC-ROC : {auc_roc:.4f}")

    # Feature importances
    print("\nFeature importances (gain):")
    imps = model.feature_importances_
    pairs = sorted(zip(feature_cols, imps), key=lambda t: t[1], reverse=True)
    for name, imp in pairs:
        bar = "█" * int(imp * 60)
        print(f"  {name:<22} {imp:.4f}  {bar}")

    # Save model
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(model, fh)
    print(f"\nModel saved → {MODEL_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
