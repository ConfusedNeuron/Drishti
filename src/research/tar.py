"""Two-regime Threshold Autoregression (Tsay/Tong; SAAPM Wk4). Python analogue of
NTS::tar() + thr.test(): grid-search the threshold on the delay-d lagged value to
minimize combined SSR of two AR(p) fits, then a bootstrap likelihood-ratio test
of the two-regime model against a single linear AR(p)."""
from __future__ import annotations
import numpy as np
import pandas as pd


def _design(y: np.ndarray, p: int, d: int):
    """(X, Y, Z): X = AR(p) design with intercept, Y = target, Z = delay-d threshold var, aligned."""
    start = max(p, d)
    n = len(y)
    Y = y[start:n]
    X = np.column_stack([np.ones(n - start)] + [y[start - k:n - k] for k in range(1, p + 1)])
    Z = y[start - d:n - d]
    return X, Y, Z


def _ols_ssr(X: np.ndarray, Y: np.ndarray):
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    resid = Y - X @ beta
    return beta, float(resid @ resid)


def fit_tar(series: pd.Series, p: int = 1, d: int = 1, trim: float = 0.15) -> dict:
    y = series.dropna().to_numpy()
    X, Y, Z = _design(y, p, d)
    lo, hi = np.quantile(Z, [trim, 1 - trim])
    cands = np.unique(Z[(Z >= lo) & (Z <= hi)])
    best = None
    for thr in cands:
        m = Z <= thr
        if m.sum() < p + 2 or (~m).sum() < p + 2:
            continue
        b1, s1 = _ols_ssr(X[m], Y[m])      # lower regime (Z <= thr)
        b2, s2 = _ols_ssr(X[~m], Y[~m])    # upper regime (Z > thr)
        ssr = s1 + s2
        if best is None or ssr < best["ssr"]:
            best = {"threshold": float(thr), "lower_coef": b1, "upper_coef": b2,
                    "ssr": ssr, "n_lower": int(m.sum()), "n_upper": int((~m).sum())}
    if best is None:                       # all candidates under-populated (degenerate series)
        raise ValueError("No valid threshold found (regimes under-populated); reduce trim/p or check series.")
    _, lin_ssr = _ols_ssr(X, Y)
    best["linear_ssr"] = lin_ssr
    best["aic"] = len(Y) * np.log(best["ssr"] / len(Y)) + 2 * (2 * (p + 1) + 1)
    return best


def threshold_test(series: pd.Series, p: int = 1, d: int = 1, trim: float = 0.15,
                   n_boot: int = 200, seed: int = 0) -> dict:
    """Bootstrap LR test: H0 linear AR(p) vs H1 two-regime TAR. LR = n*ln(SSR0/SSR1)."""
    y = series.dropna().to_numpy()
    X, Y, _ = _design(y, p, d)
    fit = fit_tar(series, p, d, trim)
    lr = len(Y) * np.log(fit["linear_ssr"] / fit["ssr"])
    beta0, _ = _ols_ssr(X, Y)
    resid0 = Y - X @ beta0
    rng = np.random.default_rng(seed)
    start = max(p, d)
    attempted, count = 0, 0
    for _ in range(n_boot):
        yb = y.copy()
        eb = rng.choice(resid0, size=len(Y), replace=True)
        for i, t in enumerate(range(start, len(y))):
            pred = beta0[0] + sum(beta0[k] * yb[t - k] for k in range(1, p + 1))
            yb[t] = pred + eb[i]
        try:
            fb = fit_tar(pd.Series(yb), p, d, trim)
        except ValueError:                 # degenerate replicate -> skip, keep denominator honest
            continue
        attempted += 1
        lrb = len(Y) * np.log(fb["linear_ssr"] / fb["ssr"])
        if lrb >= lr:
            count += 1
    return {"lr_stat": float(lr), "p_value": (count + 1) / (attempted + 1),
            "threshold": fit["threshold"]}
