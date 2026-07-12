"""Copilot routes — deterministic memo + optional LLM."""
from __future__ import annotations
import dataclasses
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.dashboard.json_safe import clean_json
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

    # Inject cached news sentiment if available (12-hour freshness)
    from pathlib import Path
    from src.config import DATA_DIR
    from src.research.news import load_cached_sentiment
    import dataclasses
    _news_cache = DATA_DIR / "cache" / "news" / "latest.json"
    _news_result = load_cached_sentiment(_news_cache)
    news_sentiment_dict = dataclasses.asdict(_news_result) if _news_result is not None else None

    memo_md = generate_memo(
        snapshot=snap,
        var_results=var_res,
        es_result=es,
        backtest=bt,
        contributions=contribs,
        stress_results=stress,
        news_sentiment=news_sentiment_dict,
    )

    return clean_json({"memo": memo_md, "missing_symbols": missing})


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

    # Refuse investment advice regardless of LLM availability
    from src.copilot.safety import is_advice_request, REFUSAL
    if is_advice_request(req.question):
        return {
            "answer": REFUSAL,
            "advice_refused": True,
            "source": "safety_filter",
        }

    if not settings.llm_api_key:
        return {
            "answer": (
                "LLM unavailable (no API key). "
                "Here is the deterministic risk summary:\n\n" + memo_text[:2000]
            ),
            "advice_refused": False,
            "source": "deterministic_memo",
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

    source = "llm"
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
        source = "llm_error"

    return {"answer": answer, "advice_refused": False, "source": source}
