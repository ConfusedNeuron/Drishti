"""Copilot routes — deterministic memo + optional LLM."""
from __future__ import annotations
import dataclasses
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.dashboard.routes.portfolio import get_snapshot
from src.risk.returns import build_return_matrix, portfolio_returns, covariance_matrix
from src.risk.var import all_var_methods
from src.risk.es import expected_shortfall
from src.risk.backtest import run_var_backtest
from src.risk.contribution import component_var
from src.risk.stress import run_all_scenarios
from src.copilot.memo import generate_memo

import numpy as np

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    style: str = "class_presentation"


@router.post("/memo")
async def memo_endpoint():
    """Generate deterministic risk memo (no LLM)."""
    snap = get_snapshot()
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=365 * 5)

    returns_df, missing = build_return_matrix(snap, start, end)
    if returns_df.empty:
        raise HTTPException(status_code=503, detail="No cached price data.")

    weights_dict = snap.weights
    common = [s for s in weights_dict if s in returns_df.columns]
    w_norm = {s: weights_dict[s] / sum(weights_dict[s] for s in common) for s in common}
    port_ret = portfolio_returns(returns_df, w_norm)
    w_arr = np.array([w_norm[s] for s in common])
    cov = covariance_matrix(returns_df[common])

    var_res = all_var_methods(port_ret, w_arr, cov, snap.total_value)
    es = expected_shortfall(port_ret, snap.total_value)
    try:
        bt = run_var_backtest(port_ret, snap.total_value)
    except ValueError:
        raise HTTPException(status_code=503, detail="Insufficient data for backtest.")
    contribs = component_var(w_arr, common, cov, snap.total_value)
    stress = run_all_scenarios(snap)

    memo_md = generate_memo(
        snapshot=snap,
        var_results=var_res,
        es_result=es,
        backtest=bt,
        contributions=contribs,
        stress_results=stress,
    )

    return {"memo": memo_md, "missing_symbols": missing}


@router.post("/ask")
async def ask_endpoint(req: AskRequest):
    """
    Experimental: use LLM (if configured) to answer a risk question.
    Falls back to relevant memo excerpt if no LLM key is available.
    """
    from src.config import settings

    snap = get_snapshot()
    memo_resp = await memo_endpoint()
    memo_text = memo_resp["memo"]

    if not settings.llm_api_key:
        return {
            "answer": (
                "LLM unavailable (no API key). "
                "Here is the deterministic risk summary:\n\n" + memo_text[:2000]
            ),
            "advice_refused": False,
            "source": "deterministic_memo",
        }

    # Refuse investment advice
    advice_keywords = ["buy", "sell", "hold", "invest", "rebalance", "allocate", "recommend"]
    if any(kw in req.question.lower() for kw in advice_keywords):
        return {
            "answer": (
                "I'm a risk analytics tool and cannot provide investment advice. "
                "I can explain your VaR, backtest results, regime status, or factor signals. "
                "What risk metric would you like to understand?"
            ),
            "advice_refused": True,
            "source": "policy",
        }

    # Build prompt from structured memo (not raw holdings)
    system_prompt = (
        "You are Drishti's portfolio risk explainer, not an investment adviser. "
        "Use ONLY the structured risk summary provided. "
        "Never recommend buying, selling, holding, or rebalancing any security. "
        "Explain: VaR (and compare methods), ES, backtest results, regime implications, "
        "component contributions, stress losses, IC/t-stat signal quality, and "
        "Granger causality findings. "
        "If asked for trade advice, refuse with one sentence and redirect to risk diagnostics."
    )

    user_content = (
        f"Risk summary:\n\n{memo_text}\n\n"
        f"User question: {req.question}"
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.llm_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        answer = response.content[0].text
    except Exception as e:
        answer = f"LLM call failed ({e}). Showing deterministic memo:\n\n{memo_text[:1500]}"

    return {"answer": answer, "advice_refused": False, "source": "llm"}
