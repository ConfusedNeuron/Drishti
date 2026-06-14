"""
Train XGBoost VaR breach classifier and save to data/cache/models/breach_classifier.pkl.

Usage:
    PYTHONPATH=. python scripts/train_breach_classifier.py

Requires: xgboost
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
from src.portfolio.importer import load_sample
from src.risk.returns import build_return_matrix
from src.research.breach_classifier import build_breach_features
from src.research.hmm import walk_forward_hmm

MODEL_PATH = DATA_DIR / "cache" / "models" / "breach_classifier.pkl"


def main() -> None:
    print("=" * 60)
    print("Drishti — XGBoost VaR Breach Classifier Training")
    print("=" * 60)

    start, end = default_dates()
    snap = load_sample()
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

    # xgboost is required for every confidence level — import once up front so a
    # missing dependency fails fast with a clear message (and a clean exit code).
    try:
        import xgboost as xgb
    except ImportError:
        print("ERROR: xgboost not installed. pip install xgboost")
        sys.exit(1)

    from sklearn.metrics import average_precision_score, roc_auc_score

    # Show BOTH VaR levels: 99% is documented as too sparse to train on this smooth
    # large-cap portfolio (leakage-free past-only threshold), 95% is the trainable
    # model the app serves. trained_models keeps each fitted estimator by level.
    CONFIDENCE_LEVELS = (0.99, 0.95)
    trained_models: dict[float, object] = {}

    for confidence in CONFIDENCE_LEVELS:
        tail_pct = (1.0 - confidence) * 100
        print("\n" + "=" * 60)
        print(
            f"=== VaR confidence: {confidence:.0%} "
            f"(breach = next-day return below the {tail_pct:.0f}% past-only quantile) ==="
        )
        print("=" * 60)

        print("Building feature matrix…")
        feat_df = build_breach_features(
            port_ret, regime_hist, factor_returns, macro_renamed, confidence=confidence
        )
        print(f"Feature matrix shape: {feat_df.shape}")

        feature_cols = [c for c in feat_df.columns if c != "breach"]
        X = feat_df[feature_cols]          # keep as DataFrame so XGBoost records feature names
        y = feat_df["breach"].values

        # Split on time order (80/20) — chronological, no shuffling.
        split = int(len(X) * 0.8)
        X_train_raw, X_test = X.iloc[:split], X.iloc[split:]
        y_train_raw, y_test = y[:split], y[split:]

        # Class distribution (training set)
        n_breach = int(y_train_raw.sum())
        n_ok = len(y_train_raw) - n_breach
        print(f"\nClass distribution (train set):")
        print(f"  Normal (0): {n_ok}  ({n_ok/len(y_train_raw)*100:.1f}%)")
        print(f"  Breach (1): {n_breach}  ({n_breach/len(y_train_raw)*100:.1f}%)")

        if n_breach < 5:
            print(
                f"FINDING: only {n_breach} breach days at {confidence:.0%} VaR — "
                "too sparse to train a reliable classifier on this portfolio "
                "(leakage-free threshold). Skipping."
            )
            continue

        # Class imbalance handled via XGBoost scale_pos_weight (reweights the gradient
        # without fabricating synthetic minority samples — SMOTE interpolates between
        # autocorrelated tail days, distorting the very tail being modeled).
        X_train, y_train = X_train_raw, y_train_raw
        scale_pos_weight = n_ok / max(n_breach, 1)
        print(f"\nscale_pos_weight (n_normal / n_breach): {scale_pos_weight:.2f}")

        print(f"\nTraining XGBoost (n_train={len(X_train)}, n_test={len(X_test)})…")

        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            eval_metric="aucpr",
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train, verbose=False)

        # Evaluation: AUC-PR
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

        trained_models[confidence] = model

    # Persist the 95% model — that is the level the app serves. If 95% was too
    # sparse to train either, do not overwrite whatever is on disk.
    print("\n" + "=" * 60)
    serve_model = trained_models.get(0.95)
    if serve_model is None:
        print("95% VaR model not trainable — nothing saved.")
        print("Done.")
        return

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as fh:
        pickle.dump(serve_model, fh)
    print(f"95% VaR model saved → {MODEL_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
