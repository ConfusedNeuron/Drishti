"""
Drishti Risk MCP Server.

Exposes six risk-analytics tools via the Model Context Protocol (FastMCP).
Tools call the pure analytics functions in src/risk/ and src/research/.

Boot standalone:
    python risk_mcp/server.py

Or register in an MCP client config (e.g. Claude Desktop):
    {
      "command": "python",
      "args": ["risk_mcp/server.py"],
      "cwd": "/path/to/drishti"
    }

Safety contract:
  - No tool returns raw holdings or price series — only computed risk metrics.
  - Prompts containing buy/sell/hold/invest/recommend language are rejected
    with a safe redirect message (enforced in risk_mcp/tools.py:_check_prompt).

Note: the directory is named risk_mcp/ (not mcp/) to avoid shadowing the
installed `mcp` PyPI package.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure drishti root is importable when the server is run as a script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.fastmcp import FastMCP

from risk_mcp.tools import (
    _check_prompt,
    calculate_portfolio_risk,
    get_var_backtest,
    get_current_regime,
    get_factor_signals,
    run_stress_test,
    generate_risk_memo,
)

mcp = FastMCP(
    name="drishti-risk",
    instructions=(
        "You are the Drishti Risk Copilot. You provide educational portfolio risk "
        "analytics for Indian equity portfolios. You answer only in terms of risk "
        "metrics and methodology — never investment advice. "
        "Requests containing buy/sell/hold/invest/recommend language will be refused."
    ),
)


# ── Tool 1 ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def calculate_portfolio_risk_tool(
    confidence: float = 0.99,
    horizon_days: int = 10,
    holdings: list[dict] | None = None,
) -> dict:
    """
    Compute Value at Risk (historical, parametric, GARCH-FHS), Expected Shortfall,
    top-5 component VaR contributors, annualised volatility, and maximum drawdown
    for the currently loaded portfolio.

    Returns computed risk metrics only — no raw prices or holdings.

    Args:
        confidence:   VaR confidence level (default 0.99 = 99%).
        horizon_days: Holding period in trading days (default 10).
        holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
            dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    return calculate_portfolio_risk(confidence=confidence, horizon_days=horizon_days, holdings=holdings)


# ── Tool 2 ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_var_backtest_tool(confidence: float = 0.99, holdings: list[dict] | None = None) -> dict:
    """
    Run Kupiec unconditional-coverage and Christoffersen independence backtests
    on a rolling 252-day historical VaR for the current portfolio.

    Returns test statistics, p-values, pass/fail flags, and a plain-English verdict.

    Args:
        confidence: VaR confidence level to backtest (default 0.99).
        holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
            dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    return get_var_backtest(confidence=confidence, holdings=holdings)


# ── Tool 3 ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_current_regime_tool(holdings: list[dict] | None = None) -> dict:
    """
    Detect the current HMM 2-state volatility regime (low-vol / high-vol) using
    a walk-forward Gaussian HMM fitted on portfolio returns.

    Returns: current regime label, posterior probability, consecutive days in regime,
    and regime-conditioned historical VaR for both states.

    Args:
        holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
            dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    return get_current_regime(holdings=holdings)


# ── Tool 4 ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_factor_signals_tool(
    prompt: str = "",
    lags: str = "1,2,3,5,10",
) -> dict:
    """
    Compute time-series Information Coefficient (IC) and Granger causality for
    commodity and macro factors vs. Indian equity sector returns.

    Returns top-15 results by |t-stat| with Benjamini-Hochberg FDR correction flags.

    Args:
        prompt: Optional natural-language context (checked for advisory keywords).
        lags:   Comma-separated lag values in trading days (default "1,2,3,5,10").
    """
    if prompt:
        safe = _check_prompt(prompt)
        if safe:
            return {"error": safe}
    return get_factor_signals(lags=lags)


# ── Tool 5 ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def run_stress_test_tool(scenario_id: str = "", holdings: list[dict] | None = None) -> dict:
    """
    Apply historical stress scenarios to the portfolio and report estimated losses.

    Available scenarios: covid_march2020, crude_shock_2022, rate_hike_100bps,
    inr_depreciation_10pct, election_volatility.

    If scenario_id is empty, all five scenarios are run.

    Args:
        scenario_id: Scenario key (leave empty for all five).
        holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
            dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    sid = scenario_id.strip() or None
    return run_stress_test(scenario_id=sid, holdings=holdings)


# ── Tool 6 ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def generate_risk_memo_tool(prompt: str = "", holdings: list[dict] | None = None) -> dict:
    """
    Generate a deterministic Markdown risk memo aggregating all available analytics:
    VaR, ES, backtest, regime, component contributions, stress scenarios, IC signals,
    and Diebold-Yilmaz connectedness.

    The memo is safe for LLM context injection — no raw holdings or prices included.

    Args:
        prompt: Optional natural-language question to check for advisory content.
        holdings: optional list of {"symbol","quantity","average_price","last_price"?,"exchange"?}
            dicts — e.g. as returned by a broker MCP (Zerodha Kite MCP).
    """
    if prompt:
        safe = _check_prompt(prompt)
        if safe:
            return {"error": safe}
    return generate_risk_memo(holdings=holdings)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
