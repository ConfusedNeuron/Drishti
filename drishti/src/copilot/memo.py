"""
Deterministic risk memo generator — no LLM required.

Produces a Markdown / HTML memo from structured risk and research outputs.
Always safe to call, even when LLM or MCP are unavailable.
"""
from __future__ import annotations
from datetime import datetime

from src.models import (
    BacktestResult, ComponentContribution, ESResult,
    PortfolioSnapshot, StressResult, VaRResult,
)


def generate_memo(
    snapshot: PortfolioSnapshot,
    var_results: dict[str, VaRResult],          # {"historical": ..., "parametric": ..., "garch_fhs": ...}
    es_result: ESResult,
    backtest: BacktestResult,
    regime_info: dict | None = None,
    contributions: list[ComponentContribution] | None = None,
    stress_results: list[StressResult] | None = None,
    ic_summary: list[dict] | None = None,
    spillover_total: float | None = None,
    data_source: str = "Bloomberg Terminal, FRTL, IIM Calcutta",
    style: str = "academic",
) -> str:
    """Return a Markdown memo string."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conf = es_result.confidence
    horizon = es_result.horizon_days

    lines = [
        f"# Drishti Risk & Research Memo",
        f"",
        f"> Generated: {now} | Data source: {data_source}",
        f"> **Disclaimer:** For educational risk analytics only. Not investment advice.",
        f"",
        f"---",
        f"",
        f"## 1. Portfolio Summary",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Portfolio ID | {snapshot.portfolio_id} |",
        f"| Total value | ₹{snapshot.total_value:,.0f} |",
        f"| Holdings | {len(snapshot.modeled_holdings)} modeled |",
        f"| Source | {snapshot.source} |",
        f"",
    ]

    # VaR section
    lines += [
        f"## 2. Value at Risk ({conf*100:.0f}% confidence, {horizon}-day horizon)",
        f"",
        f"| Method | VaR (₹) | VaR (%) | Notes |",
        f"|--------|---------|---------|-------|",
    ]
    method_notes = {
        "historical":  "Empirical quantile; non-overlapping windows for multi-day",
        "parametric":  "Assumes normal returns; √t horizon scaling",
        "garch_fhs":   "GARCH(1,1) filtered; fat-tailed; bootstrapped residuals",
    }
    for method, vr in var_results.items():
        note = method_notes.get(method, "")
        lines.append(f"| {method.replace('_',' ').title()} | ₹{vr.amount:,.0f} | {vr.percent:.2%} | {note} |")

    lines += [
        f"",
        f"**Expected Shortfall ({conf*100:.0f}%, {horizon}d):** ₹{es_result.amount:,.0f} "
        f"({es_result.percent:.2%}), based on {es_result.tail_obs} tail observations."
        + (" ⚠️ Unstable — fewer than 30 tail obs." if es_result.unstable else ""),
        f"",
    ]

    # Backtest section
    kup = backtest.kupiec
    chr_ = backtest.christoffersen
    lines += [
        f"## 3. VaR Model Backtest",
        f"",
        f"| Test | Stat | p-value | Result |",
        f"|------|------|---------|--------|",
        f"| Kupiec (unconditional coverage) | {kup.lr_statistic:.3f} | {kup.p_value:.3f} | {'✅ Pass' if kup.pass_ else '❌ Fail'} |",
        f"| Christoffersen (independence) | {chr_.lr_statistic:.3f} | {chr_.p_value:.3f} | {'✅ Pass' if chr_.pass_ else '❌ Fail'} |",
        f"",
        f"- Observed violations: **{kup.violations}** vs expected **{kup.expected_violations:.1f}** "
        f"({kup.violation_rate:.2%} vs {kup.expected_rate:.2%})",
        f"- {chr_.finding}",
        f"- **Verdict:** {backtest.verdict}",
        f"",
    ]

    # Regime section
    if regime_info:
        current = regime_info.get("current_label", "unknown")
        consec = regime_info.get("consecutive_days", "?")
        low = regime_info.get("low_vol")
        high = regime_info.get("high_vol")
        lines += [
            f"## 4. Volatility Regime (HMM 2-State)",
            f"",
            f"Current regime: **{current.upper().replace('_', '-')}** "
            f"({consec} consecutive trading days)",
            f"",
        ]
        if low and high:
            lines += [
                f"| Regime | VaR ({conf*100:.0f}%, {horizon}d) | Obs |",
                f"|--------|---------|-----|",
                f"| Low-Vol | ₹{low['var_amount']:,.0f} ({low['var_percent']:.2%}) | {low['obs']} |",
                f"| High-Vol | ₹{high['var_amount']:,.0f} ({high['var_percent']:.2%}) | {high['obs']} |",
                f"",
            ]

    # Component VaR
    if contributions:
        lines += [
            f"## 5. Top Risk Contributors (Component VaR)",
            f"",
            f"| Symbol | Weight | Component VaR | VaR Share |",
            f"|--------|--------|--------------|-----------|",
        ]
        for c in contributions[:5]:
            lines.append(
                f"| {c.symbol} | {c.weight:.1%} | ₹{c.component_var:,.0f} | {c.var_share:.1%} |"
            )
        lines.append("")

    # Stress tests
    if stress_results:
        lines += [
            f"## 6. Stress Scenarios",
            f"",
            f"| Scenario | Loss (₹) | Loss (%) |",
            f"|----------|----------|----------|",
        ]
        for s in stress_results:
            lines.append(
                f"| {s.description} | ₹{s.portfolio_loss:,.0f} | {s.loss_percent:.2%} |"
            )
        lines.append("")

    # Research highlights
    if ic_summary:
        lines += [
            f"## 7. Commodity Factor Signals (Top 5 by |t-stat|)",
            f"",
            f"| Factor | Target | Lag | IC | t-stat | BH-Sig |",
            f"|--------|--------|-----|----|--------|--------|",
        ]
        for ic in ic_summary[:5]:
            lines.append(
                f"| {ic['factor']} | {ic['target']} | {ic['lag_days']}d "
                f"| {ic['ic_mean']:.3f} | {ic['t_stat']:.2f} "
                f"| {'✅' if ic.get('bh_significant') else '—'} |"
            )
        lines += [
            f"",
            f"*BH-Sig = significant after Benjamini-Hochberg FDR correction (α=0.05).*",
            f"",
        ]

    if spillover_total is not None:
        lines += [
            f"**Diebold-Yilmaz Total Connectedness Index:** {spillover_total:.1f}%",
            f"(% of forecast-error variance explained by cross-market shocks)",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"*Drishti — Bloomberg-powered, backtest-validated portfolio risk analytics.*",
        f"*IIM Calcutta PGDBA, Financial Risk Management, {datetime.now().year}.*",
    ]

    return "\n".join(lines)
