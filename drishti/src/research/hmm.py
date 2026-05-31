"""
HMM 2-state volatility regime detection.

Key design decisions:
  - Canonical state labeling: state 0 = low-vol, state 1 = high-vol.
    After each fit, states are relabeled by emission mean of rolling_vol feature.
    This prevents label-switching across walk-forward refits.
  - Walk-forward fitting: at each refit date, only past data is used.
    OOS regime labels are stored; in-sample labels are discarded.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _canonical_labels(model, states: np.ndarray, vol_feature_idx: int = 0) -> np.ndarray:
    """Remap states so that state 0 = lowest emission mean on vol_feature_idx."""
    means = model.means_[:, vol_feature_idx]
    sort_order = np.argsort(means)   # sort_order[0] = current state with lowest mean
    remap = {int(sort_order[i]): i for i in range(len(sort_order))}
    return np.array([remap[int(s)] for s in states])


def build_hmm_features(
    portfolio_returns: pd.Series,
    vix_series: pd.Series | None = None,
    window: int = 20,
) -> pd.DataFrame:
    """
    Features for HMM:
      - rolling_vol: 20-day rolling std of portfolio returns (annualized)
      - rolling_abs_ret: 20-day rolling mean absolute return
      - vix_level: India VIX level (optional)
      - vix_change: 5-day VIX change (optional)
    """
    r = portfolio_returns.copy()
    feats = pd.DataFrame(index=r.index)
    feats["rolling_vol"] = r.rolling(window).std() * np.sqrt(252)
    feats["rolling_abs_ret"] = r.abs().rolling(window).mean()

    if vix_series is not None:
        vix = vix_series.reindex(r.index).ffill()
        feats["vix_level"] = vix
        feats["vix_change"] = vix.diff(5)

    return feats.dropna()


def fit_hmm(features: pd.DataFrame, n_states: int = 2, n_iter: int = 200) -> dict:
    """
    Fit a Gaussian HMM and return model + canonically-labeled state sequence.

    Returns dict with:
      model       — fitted GaussianHMM
      states      — ndarray of regime labels (0=low-vol, 1=high-vol)
      dates       — DatetimeIndex aligned with states
      probs       — posterior probabilities (n_obs, n_states)
      means       — emission means per state (for display)
    """
    from hmmlearn.hmm import GaussianHMM

    X = features.values
    model = GaussianHMM(n_components=n_states, covariance_type="full",
                        n_iter=n_iter, random_state=42)
    model.fit(X)
    raw_states = model.predict(X)
    probs = model.predict_proba(X)

    states = _canonical_labels(model, raw_states, vol_feature_idx=0)

    return {
        "model": model,
        "states": states,
        "dates": features.index,
        "probs": probs,
        "means": model.means_,
        "feature_names": list(features.columns),
    }


def walk_forward_hmm(
    portfolio_returns: pd.Series,
    vix_series: pd.Series | None = None,
    min_train_days: int = 252,
    refit_freq: int = 21,   # trading days between refits (~1 month)
    window: int = 20,
) -> pd.DataFrame:
    """
    Walk-forward regime detection.
    At each refit point, fit HMM on all past data, predict regime for next period.

    Returns DataFrame with columns: regime, prob_high_vol
    Index aligned with portfolio_returns (OOS portion only).
    """
    features = build_hmm_features(portfolio_returns, vix_series, window=window)
    dates = features.index
    n = len(dates)

    results = {}

    t = min_train_days
    while t < n:
        train_feats = features.iloc[:t]
        try:
            fit = fit_hmm(train_feats)
        except Exception:
            t += refit_freq
            continue

        model = fit["model"]
        predict_end = min(t + refit_freq, n)
        oos_feats = features.iloc[t:predict_end]

        if len(oos_feats) == 0:
            break

        raw_oos = model.predict(oos_feats.values)
        oos_probs = model.predict_proba(oos_feats.values)
        oos_states = _canonical_labels(model, raw_oos, vol_feature_idx=0)

        for i, date in enumerate(oos_feats.index):
            results[date] = {
                "regime": int(oos_states[i]),
                "prob_high_vol": float(oos_probs[i, 1] if oos_probs.shape[1] > 1 else oos_probs[i, 0]),
            }
        t = predict_end

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results).T
    df.index = pd.DatetimeIndex(df.index)
    df["regime"] = df["regime"].astype(int)
    return df


def regime_conditioned_var(
    portfolio_returns: pd.Series,
    regime_history: pd.DataFrame,
    portfolio_value: float,
    confidence: float = 0.99,
) -> dict:
    """
    Compute historical VaR separately for each regime.
    regime_history: DataFrame with 'regime' column, DatetimeIndex.
    """
    alpha = 1 - confidence
    results = {}

    for state in [0, 1]:
        label = "low_vol" if state == 0 else "high_vol"
        mask = regime_history["regime"] == state
        regime_dates = regime_history[mask].index
        r_regime = portfolio_returns.reindex(regime_dates).dropna()

        if len(r_regime) < 30:
            results[label] = None
            continue

        var_ret = float(np.percentile(r_regime.values, alpha * 100))
        results[label] = {
            "var_amount": abs(var_ret * portfolio_value),
            "var_percent": abs(var_ret),
            "obs": len(r_regime),
        }

    # Current regime
    current_regime = int(regime_history["regime"].iloc[-1]) if not regime_history.empty else 0
    current_label = "low_vol" if current_regime == 0 else "high_vol"

    # Consecutive days in current regime
    regimes = regime_history["regime"].values
    consec = 1
    for i in range(len(regimes) - 2, -1, -1):
        if regimes[i] == current_regime:
            consec += 1
        else:
            break

    return {
        "current_regime": current_regime,
        "current_label": current_label,
        "consecutive_days": consec,
        "low_vol": results.get("low_vol"),
        "high_vol": results.get("high_vol"),
    }
