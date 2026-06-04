"""
Tests for src/research/news.py and NewsSentimentResult / NewsHeadline dataclasses.

All tests are purely local — no network calls, no model downloads.
"""
from __future__ import annotations

import dataclasses
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.models import NewsHeadline, NewsSentimentResult
from src.research.news import (
    _source_label,
    aggregate_sentiment,
    fetch_headlines,
    load_cached_sentiment,
    save_sentiment_cache,
)


# ── _source_label ─────────────────────────────────────────────────────────

def test_source_label_et():
    assert _source_label("https://economictimes.indiatimes.com/markets/rss.cms") == "ET Markets"


def test_source_label_sebi():
    assert _source_label("https://www.sebi.gov.in/sebi_data/rss/rss_sebi.xml") == "SEBI"


def test_source_label_unknown_falls_back_to_hostname():
    label = _source_label("https://example.com/feed")
    assert "example.com" in label


# ── aggregate_sentiment ────────────────────────────────────────────────────

def _hl(label: str, score: float = 0.9) -> NewsHeadline:
    return NewsHeadline(
        title="test", link="", published="", source="test",
        sentiment_label=label, sentiment_score=score,
    )


def test_aggregate_all_positive():
    headlines = [_hl("positive")] * 5
    assert aggregate_sentiment(headlines) == "Bullish"


def test_aggregate_all_negative():
    headlines = [_hl("negative")] * 5
    assert aggregate_sentiment(headlines) == "Bearish"


def test_aggregate_all_neutral():
    headlines = [_hl("neutral")] * 5
    assert aggregate_sentiment(headlines) == "Neutral"


def test_aggregate_empty():
    assert aggregate_sentiment([]) == "Neutral"


def test_aggregate_mixed_majority_positive():
    # 7 positive, 3 negative — clear majority
    headlines = [_hl("positive")] * 7 + [_hl("negative")] * 3
    assert aggregate_sentiment(headlines) == "Bullish"


def test_aggregate_mixed_majority_negative():
    headlines = [_hl("negative")] * 7 + [_hl("positive")] * 3
    assert aggregate_sentiment(headlines) == "Bearish"


def test_aggregate_near_tie_returns_neutral():
    # 5 positive, 5 negative — weighted scores equal → Neutral
    headlines = [_hl("positive")] * 5 + [_hl("negative")] * 5
    result = aggregate_sentiment(headlines)
    assert result == "Neutral"


# ── Cache round-trip ───────────────────────────────────────────────────────

def _make_result(aggregate: str = "Bullish") -> NewsSentimentResult:
    headlines = [
        NewsHeadline(
            title="Markets rally on RBI dovish signal",
            link="https://example.com/1",
            published="Thu, 05 Jun 2025 09:00:00 +0000",
            source="ET Markets",
            sentiment_label="positive",
            sentiment_score=0.92,
        ),
        NewsHeadline(
            title="SEBI probes derivatives manipulation",
            link="https://example.com/2",
            published="Thu, 05 Jun 2025 08:30:00 +0000",
            source="SEBI",
            sentiment_label="negative",
            sentiment_score=0.88,
        ),
    ]
    return NewsSentimentResult(
        headlines=headlines,
        aggregate=aggregate,
        positive_pct=50.0,
        negative_pct=50.0,
        neutral_pct=0.0,
        fetched_at=datetime.now(tz=timezone.utc).isoformat(),
        n_sources=2,
    )


def test_save_and_load_cache():
    result = _make_result("Bullish")
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "news" / "latest.json"
        save_sentiment_cache(result, cache_path)
        assert cache_path.exists()
        loaded = load_cached_sentiment(cache_path)
        assert loaded is not None
        assert loaded.aggregate == "Bullish"
        assert len(loaded.headlines) == 2
        assert loaded.headlines[0].title == "Markets rally on RBI dovish signal"


def test_load_cache_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "does_not_exist.json"
        assert load_cached_sentiment(cache_path) is None


def test_load_cache_stale_returns_none():
    result = _make_result()
    # Back-date the fetched_at by 13 hours (> 12h threshold)
    stale_time = datetime.now(tz=timezone.utc) - timedelta(hours=13)
    result.fetched_at = stale_time.isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "latest.json"
        save_sentiment_cache(result, cache_path)
        assert load_cached_sentiment(cache_path) is None


def test_load_cache_fresh_returns_result():
    result = _make_result()
    # 30 minutes old — well within 12h window
    fresh_time = datetime.now(tz=timezone.utc) - timedelta(minutes=30)
    result.fetched_at = fresh_time.isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "latest.json"
        save_sentiment_cache(result, cache_path)
        loaded = load_cached_sentiment(cache_path)
        assert loaded is not None
        assert loaded.n_sources == 2


def test_cache_json_is_valid():
    result = _make_result()
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "latest.json"
        save_sentiment_cache(result, cache_path)
        parsed = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "headlines" in parsed
        assert "aggregate" in parsed
        assert "fetched_at" in parsed


def test_dataclass_asdict_round_trip():
    result = _make_result()
    d = dataclasses.asdict(result)
    restored = NewsSentimentResult(
        headlines=[NewsHeadline(**h) for h in d["headlines"]],
        aggregate=d["aggregate"],
        positive_pct=d["positive_pct"],
        negative_pct=d["negative_pct"],
        neutral_pct=d["neutral_pct"],
        fetched_at=d["fetched_at"],
        n_sources=d["n_sources"],
    )
    assert restored.aggregate == result.aggregate
    assert len(restored.headlines) == len(result.headlines)
