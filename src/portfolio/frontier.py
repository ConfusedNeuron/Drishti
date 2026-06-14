"""Markowitz mean-variance optimization (FRM Wk1). Inputs are an annualized mean
vector and annualized covariance matrix. Long-only by default via SLSQP bounds.
Diagnostic only (not investment advice)."""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize

_OPTS = {"ftol": 1e-12, "maxiter": 500}


def _bounds(n: int, long_only: bool):
    return [(0.0, 1.0)] * n if long_only else [(-1.0, 1.0)] * n


def min_variance(cov: np.ndarray, long_only: bool = True) -> np.ndarray:
    n = cov.shape[0]
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1},)
    res = minimize(lambda w: w @ cov @ w, np.repeat(1 / n, n), method="SLSQP",
                   bounds=_bounds(n, long_only), constraints=cons, options=_OPTS)
    return res.x


def _target_min_var(mu, cov, target, long_only):
    n = cov.shape[0]
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1},
            {"type": "eq", "fun": lambda w: w @ mu - target})
    return minimize(lambda w: w @ cov @ w, np.repeat(1 / n, n), method="SLSQP",
                    bounds=_bounds(n, long_only), constraints=cons, options=_OPTS)


def efficient_frontier(mu: np.ndarray, cov: np.ndarray, n_points: int = 30,
                       long_only: bool = True) -> dict:
    w_mv = min_variance(cov, long_only)
    lo = float(w_mv @ mu)
    hi = float(mu.max())
    targets = np.linspace(lo, hi, n_points)
    rets, weights, varis = [], [], []
    for i, t in enumerate(targets):
        if i == 0:
            w = w_mv                                 # anchor first point to the true min-var portfolio
        else:
            res = _target_min_var(mu, cov, t, long_only)
            if (not res.success) or abs(res.x.sum() - 1) > 1e-4 or abs(res.x @ mu - t) > 1e-4:
                continue                             # skip infeasible / non-converged target
            w = res.x
        varis.append(float(w @ cov @ w))
        rets.append(float(w @ mu))
        weights.append(w)
    # frontier variance is theoretically non-decreasing above min-var; clamp solver noise
    varis = np.maximum.accumulate(np.array(varis))
    return {"risk": np.sqrt(varis), "ret": np.array(rets), "weights": weights}


def tangency(mu: np.ndarray, cov: np.ndarray, rf: float = 0.0,
             long_only: bool = True) -> np.ndarray:
    n = cov.shape[0]
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1},)

    def neg_sharpe(w):
        ret = w @ mu - rf
        vol = np.sqrt(w @ cov @ w)
        return -ret / vol if vol > 0 else 1e6

    res = minimize(neg_sharpe, np.repeat(1 / n, n), method="SLSQP",
                   bounds=_bounds(n, long_only), constraints=cons, options=_OPTS)
    return res.x
