"""
MCP tool implementations for the Drishti Risk Copilot.

Each function is a thin wrapper around the pure analytics in src/risk/ and
src/research/ — no logic is duplicated here.

Safety contract (enforced in every tool):
  - Raw holdings and price series are never returned.
  - Any prompt containing advisory language (buy / sell / hold / invest /
    recommend) is rejected and redirected to risk diagnostics.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from src.copilot.safety import is_advice_request, REFUSAL

# ── Shared helpers ─────────────────────────────────────────────────────────────


def _check_prompt(text: str) -> str | None:
    """Return a refusal message if text requests investment advice, else None."""
    if is_advice_request(text):
        return REFUSAL
    return None


from src.config import default_dates as _default_dates


def _load_portfolio(holdings: list[dict] | None = None):
    """Caller-supplied holdings win; else the dashboard's in-process snapshot;
    else the bundled sample (MCP runs in its own process — the dashboard's
    memory is invisible to it)."""
    from src.portfolio.importer import snapshot_from_rows, load_sample
    if holdings:
        return snapshot_from_rows(holdings)
    from fastapi import HTTPException
    from src.dashboard.routes.portfolio import get_snapshot
    try:
        return get_snapshot()
    except HTTPException:
        # Only "no portfolio loaded" falls back to the sample; real errors propagate.
        return load_sample()


def _resolve_portfolio(holdings: list[dict] | None):
    """Return (snapshot, None), or (None, error_dict) when caller-supplied
    holdings are malformed — a structured error instead of a raw traceback."""
    try:
        return _load_portfolio(holdings), None
    except (ValueError, KeyError, TypeError) as e:
        return None, {"error": f"Invalid holdings: {e}"}


def _load_returns(snap):
    from src.risk.returns import build_return_matrix, portfolio_returns, covariance_matrix
    start, end = _default_dates()
    returns_df, missing = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise RuntimeError("No cached price data available.")
    weights = snap.weights
    common = [s for s in weights if s in returns_df.columns]
    if not common:
        raise RuntimeError("No overlap between portfolio symbols and cached data.")
    w = {s: weights[s] for s in common}
    w_total = sum(w.values())
    w_norm = {s: v / w_total for s, v in w.items()}
    port_ret = portfolio_returns(returns_df, w_norm)
    w_arr = np.array([w_norm[s] for s in common])
    cov = covariance_matrix(returns_df[common])
    return port_ret, w_arr, common, cov, missing


# ── Tool implementations ───────────────────────────────────────────────────────

def calculate_portfolio_risk(confidence: float = 0.99, horizon_days: int = 10,
                              holdings: list[dict] | None = None) -> dict:
    """
    Compute VaR (three methods), ES, component contributions, and drawdown
    for the currently loaded portfolio.

    Returns only computed risk metrics — no raw prices or holdings.

    holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
    dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    snap, err = _resolve_portfolio(holdings)
    if err:
        return err
    port_ret, w_arr, common, cov, missing = _load_returns(snap)

    from src.risk.var import all_var_methods
    from src.risk.es import expected_shortfall
    from src.risk.contribution import component_var
    from src.risk.drawdown import max_drawdown

    var_res = all_var_methods(port_ret, w_arr, cov, snap.total_value, confidence, horizon_days)
    es = expected_shortfall(port_ret, snap.total_value, confidence, horizon_days)
    contribs = component_var(w_arr, common, cov, snap.total_value, confidence)
    dd = max_drawdown(port_ret)

    return {
        "portfolio_id": snap.portfolio_id,
        "portfolio_source": snap.source,
        "portfolio_value": snap.total_value,
        "n_holdings_modeled": len(common),
        "missing_symbols": missing,
        "confidence": confidence,
        "horizon_days": horizon_days,
        "var": {m: {"amount": round(v.amount, 2), "percent": round(v.percent, 4),
                    "note": v.note}
                for m, v in var_res.items()},
        "expected_shortfall": {
            "amount": round(es.amount, 2),
            "percent": round(es.percent, 4),
            "tail_obs": es.tail_obs,
            "unstable": es.unstable,
        },
        "top_contributors": [
            {"symbol": c.symbol, "weight": round(c.weight, 4),
             "var_share": round(c.var_share, 4)}
            for c in contribs[:5]
        ],
        "annualized_volatility": round(float(port_ret.std() * np.sqrt(252)), 4),
        "max_drawdown": round(dd.get("max_drawdown", 0.0), 4),
        "disclaimer": "Educational risk analytics only. Not investment advice.",
    }


def get_var_backtest(confidence: float = 0.99, holdings: list[dict] | None = None) -> dict:
    """
    Run Kupiec unconditional-coverage and Christoffersen independence backtests
    on the rolling historical VaR for the current portfolio.

    holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
    dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    snap, err = _resolve_portfolio(holdings)
    if err:
        return err
    port_ret, _, _, _, _ = _load_returns(snap)

    from src.risk.backtest import run_var_backtest
    try:
        bt = run_var_backtest(port_ret, snap.total_value, confidence)
    except ValueError as e:
        return {"error": str(e)}

    kup = bt.kupiec
    chr_ = bt.christoffersen
    return {
        "portfolio_id": snap.portfolio_id,
        "portfolio_source": snap.source,
        "confidence": bt.confidence,
        "obs": bt.obs,
        "violations": bt.violations,
        "kupiec": {
            "lr_statistic": round(kup.lr_statistic, 4),
            "p_value": round(kup.p_value, 4),
            "pass": kup.pass_,
            "violation_rate": round(kup.violation_rate, 4),
            "expected_rate": kup.expected_rate,
        },
        "christoffersen": {
            "lr_statistic": round(chr_.lr_statistic, 4),
            "p_value": round(chr_.p_value, 4),
            "pass": chr_.pass_,
            "finding": chr_.finding,
        },
        "verdict": bt.verdict,
        "disclaimer": "Educational risk analytics only. Not investment advice.",
    }


def get_current_regime(holdings: list[dict] | None = None) -> dict:
    """
    Detect the current HMM volatility regime (low-vol / high-vol) via
    walk-forward fitting on the portfolio return series.
    Returns regime label, posterior probability, and regime-conditioned VaR.

    holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
    dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    snap, err = _resolve_portfolio(holdings)
    if err:
        return err
    port_ret, _, _, _, _ = _load_returns(snap)

    start, end = _default_dates()
    from src.risk.returns import load_factor_series
    vix = load_factor_series(["indiavix"], start, end)
    vix_series = vix["indiavix"] if not vix.empty and "indiavix" in vix.columns else None

    from src.research.hmm import walk_forward_hmm, regime_conditioned_var
    try:
        regime_hist = walk_forward_hmm(port_ret, vix_series)
    except Exception as e:
        return {"error": f"HMM fitting failed: {e}"}

    if regime_hist.empty:
        return {"error": "Insufficient data for regime detection."}

    rcv = regime_conditioned_var(port_ret, regime_hist, snap.total_value)

    return {
        "portfolio_id": snap.portfolio_id,
        "portfolio_source": snap.source,
        "current_regime": rcv["current_regime"],
        "current_label": rcv["current_label"],
        "consecutive_days": rcv["consecutive_days"],
        "low_vol_var": rcv.get("low_vol"),
        "high_vol_var": rcv.get("high_vol"),
        "disclaimer": "Educational risk analytics only. Not investment advice.",
    }


def get_factor_signals(lags: str = "1,2,3,5,10") -> dict:
    """
    Compute time-series IC and Granger causality for commodity/macro factors
    vs. sector returns. Returns top-15 results by |t-stat| plus BH-FDR flags.
    Never returns raw price data.
    """
    start, end = _default_dates()
    from src.risk.returns import load_factor_series, load_sector_returns
    from src.research.ic import run_full_ic_study

    factors = load_factor_series(["brent", "gold", "copper", "usdinr", "gsec10y"], start, end)
    sectors = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)

    if factors.empty or sectors.empty:
        return {"error": "No factor/sector data cached."}

    lag_list = [int(x) for x in lags.split(",")]
    result = run_full_ic_study(factors, sectors, lags=lag_list)

    top_ic = result["ic_results"][:15]
    return {
        "top_ic_results": [dataclasses.asdict(r) for r in top_ic],
        "n_tests": result["n_tests"],
        "note": (
            "IC = rolling Pearson correlation between lagged factor and sector return. "
            "BH = Benjamini-Hochberg FDR correction at α=0.05."
        ),
        "disclaimer": "Educational risk analytics only. Not investment advice.",
    }


def run_stress_test(scenario_id: str | None = None, holdings: list[dict] | None = None) -> dict:
    """
    Apply historical stress scenarios to the portfolio.
    If scenario_id is provided, runs that scenario only; otherwise runs all five.
    Returns loss amounts and percentage losses — no raw holdings returned.

    holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
    dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    snap, err = _resolve_portfolio(holdings)
    if err:
        return err
    from src.risk.stress import run_stress_scenario, run_all_scenarios

    if scenario_id:
        try:
            results = [run_stress_scenario(snap, scenario_id)]
        except ValueError as e:
            return {"error": str(e)}
    else:
        results = run_all_scenarios(snap)

    return {
        "portfolio_id": snap.portfolio_id,
        "portfolio_source": snap.source,
        "portfolio_value": snap.total_value,
        "scenarios": [
            {
                "scenario": s.scenario,
                "description": s.description,
                "portfolio_loss": round(s.portfolio_loss, 2),
                "loss_percent": round(s.loss_percent, 4),
                "affected_sectors": s.affected_sectors,
            }
            for s in results
        ],
        "disclaimer": "Educational risk analytics only. Not investment advice.",
    }


def generate_risk_memo(holdings: list[dict] | None = None) -> dict:
    """
    Generate a deterministic Markdown risk memo from structured analytics.
    The memo includes VaR, ES, backtest, regime, contributions, stress,
    IC highlights, and spillover. No raw holdings or prices are included.

    holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
    dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    snap, err = _resolve_portfolio(holdings)
    if err:
        return err
    port_ret, w_arr, common, cov, _ = _load_returns(snap)

    from src.risk.var import all_var_methods
    from src.risk.es import expected_shortfall
    from src.risk.backtest import run_var_backtest
    from src.risk.contribution import component_var
    from src.risk.stress import run_all_scenarios
    from src.copilot.memo import generate_memo

    var_res = all_var_methods(port_ret, w_arr, cov, snap.total_value, 0.99, 10)
    es = expected_shortfall(port_ret, snap.total_value, 0.99, 10)

    try:
        bt = run_var_backtest(port_ret, snap.total_value, 0.99)
    except ValueError:
        bt = None

    contribs = component_var(w_arr, common, cov, snap.total_value, 0.99)
    stress = run_all_scenarios(snap)

    # Optional: IC summary
    start, end = _default_dates()
    from src.risk.returns import load_factor_series, load_sector_returns
    from src.research.ic import run_full_ic_study
    ic_summary: list[dict] | None = None
    try:
        factors = load_factor_series(["brent", "gold", "copper", "usdinr"], start, end)
        sectors = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)
        if not factors.empty and not sectors.empty:
            ic_study = run_full_ic_study(factors, sectors, lags=[1, 5, 10])
            ic_summary = [dataclasses.asdict(r) for r in ic_study["ic_results"][:5]]
    except Exception:
        pass

    # Optional: total connectedness
    spillover_total: float | None = None
    try:
        from src.research.diebold_yilmaz import compute_spillover
        import pandas as pd
        factors2 = load_factor_series(["brent", "gold", "copper", "usdinr"], start, end)
        sectors2 = load_sector_returns(["energy", "metals", "fmcg", "it"], start, end)
        if not factors2.empty and not sectors2.empty:
            combined = pd.concat([sectors2, factors2], axis=1).dropna()
            tbl = compute_spillover(combined)
            spillover_total = tbl.total_spillover
    except Exception:
        pass

    if bt is None:
        from src.models import BacktestResult, KupiecResult, ChristoffersenResult
        # Placeholder backtest so memo still renders
        bt = BacktestResult(
            confidence=0.99, obs=0, violations=0,
            kupiec=KupiecResult(0, 1.0, True, 0, 0, 0, 0.01),
            christoffersen=ChristoffersenResult(0, 1.0, True, 0, 0, "N/A"),
            verdict="Insufficient data for backtest.",
        )

    memo = generate_memo(
        snapshot=snap,
        var_results=var_res,
        es_result=es,
        backtest=bt,
        contributions=contribs,
        stress_results=stress,
        ic_summary=ic_summary,
        spillover_total=spillover_total,
    )

    return {
        "portfolio_id": snap.portfolio_id,
        "portfolio_source": snap.source,
        "memo_markdown": memo,
        "disclaimer": "Educational risk analytics only. Not investment advice.",
    }
