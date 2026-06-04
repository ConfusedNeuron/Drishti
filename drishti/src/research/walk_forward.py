"""
Walk-forward out-of-sample factor signal backtest.

Spec: notebooks/05_walk_forward_backtest.md

For each (factor, sector) pair selected by BH-significant IC (or top-5 by |t-stat|
as fallback):
  - Rolling 252-day EXPANDING training window.
  - Step forward 21 trading days (one month) at a time.
  - At the end of each training window, estimate IC direction on the training data.
  - OOS trading rule: long sector if IC estimate > 0, flat otherwise (no shorting).
  - Accumulate OOS P&L; report Sharpe, max-drawdown, win-rate, cumulative return.

Returns a WalkForwardResult dataclass (defined in src/models.py) containing:
  - per-pair BacktestMetrics (factor, target, lag, oos_sharpe, …)
  - sharpe_matrix: factor × sector Sharpe values for the heatmap
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import WalkForwardMetrics, WalkForwardResult


# ── IC estimator on a single window ───────────────────────────────────────────

def _compute_ic_on_window(
    factor: pd.Series,
    target: pd.Series,
    lag: int,
    rolling_corr_window: int = 63,
) -> float:
    """
    Estimate mean rolling IC on [factor, target] using only the supplied window.
    Returns 0.0 if there is insufficient data to compute a reliable estimate.
    """
    df = pd.concat([factor.rename("f"), target.rename("t")], axis=1).dropna()
    df["f_lagged"] = df["f"].shift(lag)
    df = df.dropna()

    if len(df) < rolling_corr_window + lag + 5:
        return 0.0

    ic = df["f_lagged"].rolling(rolling_corr_window).corr(df["t"]).dropna()
    return float(ic.mean())


# ── Single (factor, sector, lag) backtest ─────────────────────────────────────

def _walk_forward_single(
    factor_series: pd.Series,
    target_series: pd.Series,
    lag: int,
    min_train_days: int = 252,
    refit_freq: int = 21,
) -> WalkForwardMetrics | None:
    """
    Walk-forward backtest for one (factor, sector, lag) triple.

    Expanding training window: all data up to t used to estimate IC direction.
    OOS window: next refit_freq trading days.
    Position: 1 (long) if IC > 0, 0 (flat) otherwise.  No shorting.
    """
    factor_name = factor_series.name or "factor"
    target_name = target_series.name or "target"

    df = pd.concat([
        factor_series.rename("factor"),
        target_series.rename("target"),
    ], axis=1).dropna()

    n = len(df)
    # Need enough data for at least 3 OOS periods
    if n < min_train_days + refit_freq * 3:
        return None

    oos_returns: list[float] = []
    oos_dates: list[pd.Timestamp] = []

    t = min_train_days
    while t < n:
        train = df.iloc[:t]
        ic_est = _compute_ic_on_window(train["factor"], train["target"], lag)

        oos_end = min(t + refit_freq, n)
        oos_slice = df.iloc[t:oos_end]

        position = 1.0 if ic_est > 0 else 0.0
        oos_returns.extend((oos_slice["target"].values * position).tolist())
        oos_dates.extend(list(oos_slice.index))

        t = oos_end

    if not oos_returns:
        return None

    oos = pd.Series(oos_returns, index=pd.DatetimeIndex(oos_dates))
    cum_ret = (1 + oos).cumprod()

    sharpe = float(oos.mean() / oos.std() * np.sqrt(252)) if oos.std() > 0 else 0.0
    max_dd = float(((cum_ret - cum_ret.cummax()) / cum_ret.cummax()).min())
    win_rate = float((oos > 0).mean())
    total_ret = float(cum_ret.iloc[-1] - 1)

    return WalkForwardMetrics(
        factor=factor_name,
        target=target_name,
        lag_days=lag,
        oos_sharpe=round(sharpe, 3),
        oos_max_dd=round(max_dd, 4),
        oos_win_rate=round(win_rate, 3),
        oos_total_return=round(total_ret, 4),
        oos_obs=len(oos),
        cumulative_return_dates=[str(d.date()) for d in cum_ret.index],
        cumulative_return_values=[round(float(v), 4) for v in cum_ret.values],
    )


# ── Pair selection from IC study results ──────────────────────────────────────

def _select_pairs(ic_results: list[dict]) -> list[dict]:
    """
    Select (factor, target, lag) triples to backtest.

    Prefer BH-significant pairs; fall back to top-5 by |t-stat| if none pass.
    Best lag per (factor, target) pair is the one with highest |t-stat|.
    """
    if not ic_results:
        return []

    df = pd.DataFrame(ic_results)
    bh_sig = df[df["bh_significant"]].copy()
    if bh_sig.empty:
        bh_sig = df.reindex(df["t_stat"].abs().nlargest(5).index)

    best = (
        bh_sig.assign(_abs_t=bh_sig["t_stat"].abs())
        .sort_values("_abs_t", ascending=False)
        .groupby(["factor", "target"])
        .first()
        .reset_index()
    )
    return best[["factor", "target", "lag_days"]].to_dict("records")


# ── Public API ─────────────────────────────────────────────────────────────────

def run_walk_forward(
    factor_returns_df: pd.DataFrame,
    sector_returns_df: pd.DataFrame,
    ic_results: list[dict] | None = None,
    min_train_days: int = 252,
    refit_freq: int = 21,
    default_lag: int = 1,
) -> WalkForwardResult:
    """
    Run walk-forward OOS backtest for all selected (factor, sector) pairs.

    Parameters
    ----------
    factor_returns_df : daily returns, columns = factor names
    sector_returns_df : daily returns, columns = sector names
    ic_results        : list of ICResult dicts (from run_full_ic_study).
                        If None or empty, all (factor, sector) pairs at
                        default_lag are tested.
    min_train_days    : minimum expanding-window training length (252 = 1 year)
    refit_freq        : OOS window length in trading days (21 ≈ 1 month)
    default_lag       : lag used when ic_results is not provided

    Returns
    -------
    WalkForwardResult with per-pair metrics and a factor × sector Sharpe matrix.
    """
    if ic_results:
        pairs = _select_pairs(ic_results)
    else:
        # Exhaustive grid at default_lag when no IC results available
        pairs = [
            {"factor": f, "target": t, "lag_days": default_lag}
            for f in factor_returns_df.columns
            for t in sector_returns_df.columns
        ]

    metrics: list[WalkForwardMetrics] = []

    for pair in pairs:
        fname = pair["factor"]
        tname = pair["target"]
        lag = int(pair["lag_days"])

        if fname not in factor_returns_df.columns:
            continue
        if tname not in sector_returns_df.columns:
            continue

        result = _walk_forward_single(
            factor_returns_df[fname].rename(fname),
            sector_returns_df[tname].rename(tname),
            lag=lag,
            min_train_days=min_train_days,
            refit_freq=refit_freq,
        )
        if result is not None:
            metrics.append(result)

    # Build factor × sector Sharpe matrix for heatmap
    factors = sorted({m.factor for m in metrics})
    sectors = sorted({m.target for m in metrics})
    sharpe_matrix: dict[str, dict[str, float | None]] = {
        f: {s: None for s in sectors} for f in factors
    }
    for m in metrics:
        sharpe_matrix[m.factor][m.target] = m.oos_sharpe

    return WalkForwardResult(
        metrics=metrics,
        sharpe_matrix=sharpe_matrix,
        factors=factors,
        sectors=sectors,
        n_pairs=len(metrics),
    )
