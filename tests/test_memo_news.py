"""
Tests that generate_memo() correctly injects and omits news sentiment.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.models import (
    BacktestResult, ChristoffersenResult, ComponentContribution,
    ESResult, KupiecResult, PortfolioSnapshot, VaRResult,
)
from src.copilot.memo import generate_memo


def _snapshot():
    return PortfolioSnapshot(
        portfolio_id="test", holdings=[], total_value=1_000_000, source="sample"
    )


def _var_results():
    vr = VaRResult(amount=20000, percent=0.02, confidence=0.99, horizon_days=1, method="historical")
    return {"historical": vr, "parametric": vr, "garch_fhs": vr}


def _es():
    return ESResult(amount=30000, percent=0.03, confidence=0.99, horizon_days=1, tail_obs=25)


def _backtest():
    kup = KupiecResult(lr_statistic=0.1, p_value=0.75, pass_=True, violations=5,
                       expected_violations=5.0, violation_rate=0.01, expected_rate=0.01)
    chr_ = ChristoffersenResult(lr_statistic=0.2, p_value=0.65, pass_=True,
                                pi01=0.01, pi11=0.02, finding="No clustering detected.")
    return BacktestResult(confidence=0.99, obs=500, violations=5,
                          kupiec=kup, christoffersen=chr_, verdict="Pass")


def test_memo_without_sentiment_has_no_finbert_line():
    memo = generate_memo(_snapshot(), _var_results(), _es(), _backtest())
    assert "FinBERT" not in memo
    assert "Market Sentiment" not in memo


def test_memo_with_sentiment_bullish():
    sentiment = {
        "aggregate": "Bullish",
        "positive_pct": 62.0,
        "negative_pct": 18.0,
        "headlines": [{"title": "x"}] * 35,
    }
    memo = generate_memo(_snapshot(), _var_results(), _es(), _backtest(),
                         news_sentiment=sentiment)
    assert "FinBERT" in memo
    assert "Bullish" in memo
    assert "62%" in memo or "62" in memo
    assert "18%" in memo or "18" in memo
    assert "35" in memo


def test_memo_with_sentiment_bearish():
    sentiment = {
        "aggregate": "Bearish",
        "positive_pct": 20.0,
        "negative_pct": 55.0,
        "headlines": [{"title": "x"}] * 10,
    }
    memo = generate_memo(_snapshot(), _var_results(), _es(), _backtest(),
                         news_sentiment=sentiment)
    assert "Bearish" in memo
    assert "Market Sentiment (FinBERT)" in memo


def test_memo_none_sentiment_same_as_no_kwarg():
    memo_a = generate_memo(_snapshot(), _var_results(), _es(), _backtest())
    memo_b = generate_memo(_snapshot(), _var_results(), _es(), _backtest(), news_sentiment=None)
    # Both should produce identical output (no sentiment line)
    assert memo_a == memo_b
