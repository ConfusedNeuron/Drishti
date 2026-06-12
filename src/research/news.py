"""
News RSS fetching + FinBERT sentiment scoring.

Pure functions — no side effects except explicit cache I/O in save_sentiment_cache().

Design decision: ProsusAI/finbert via transformers pipeline. Finance-domain
pre-trained BERT, gives calibrated positive/negative/neutral probabilities.
Slow (~10-30s for first call due to model loading); result is file-cached.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import feedparser

from src.models import NewsHeadline, NewsSentimentResult

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# Twelve-hour cache staleness threshold
_CACHE_MAX_AGE_HOURS = 12

# Module-level pipeline cache — loaded once, reused across calls (avoids 3–8 s
# reload penalty on every refresh even after the model is on disk).
_finbert_pipeline = None


def _get_pipeline():
    global _finbert_pipeline
    if _finbert_pipeline is None:
        from transformers import pipeline as hf_pipeline  # lazy import — large dep
        _finbert_pipeline = hf_pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
            truncation=True,
            max_length=512,
        )
    return _finbert_pipeline

DEFAULT_FEEDS: list[str] = [
    "https://economictimes.indiatimes.com/markets/rss.cms",
    "https://www.nseindia.com/rss/rss.aspx",
    "https://www.livemint.com/rss/markets",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.sebi.gov.in/sebi_data/rss/rss_sebi.xml",
    # Candidate feeds — added for coverage testing; gracefully skipped if unavailable
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.thehindubusinessline.com/markets/feeder/default.rss",
]

# RSS_FEEDS is an alias kept for backwards-compat and dry-run script imports
RSS_FEEDS = DEFAULT_FEEDS

_SOURCE_NAMES: dict[str, str] = {
    "economictimes.indiatimes.com": "ET Markets",
    "nseindia.com": "NSE",
    "livemint.com": "Mint",
    "moneycontrol.com": "MoneyControl",
    "sebi.gov.in": "SEBI",
    "business-standard.com": "Business Standard",
    "thehindubusinessline.com": "Hindu BusinessLine",
}


def _source_label(url: str) -> str:
    for domain, name in _SOURCE_NAMES.items():
        if domain in url:
            return name
    # Fallback: use the hostname
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url[:30]


def fetch_headlines(sources: list[str] | None = None) -> list[dict]:
    """
    Fetch RSS feeds and return raw headline dicts.

    Each dict has keys: title, link, published, source.
    Failed feeds are skipped gracefully — partial results are returned.
    """
    feeds = sources if sources is not None else DEFAULT_FEEDS
    headlines: list[dict] = []

    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            # feedparser never raises; bozo flag signals a malformed feed
            if parsed.get("bozo") and not parsed.get("entries"):
                log.warning("Feed skipped (bozo/empty): %s", url)
                continue
            label = _source_label(url)
            for entry in parsed.entries[:10]:
                headlines.append({
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": label,
                })
        except Exception as exc:
            log.warning("Feed fetch failed (%s): %s", url, exc)

    return headlines


def score_headlines(headlines: list[dict]) -> list[NewsHeadline]:
    """
    Run each headline title through ProsusAI/finbert.

    Returns NewsHeadline dataclasses with sentiment_label and sentiment_score.
    Heavy: first call downloads ~440 MB model if not cached by HuggingFace.
    """
    classifier = _get_pipeline()

    scored: list[NewsHeadline] = []
    for h in headlines:
        title = h.get("title", "").strip()
        if not title:
            continue
        try:
            result = classifier(title)[0]
            # FinBERT labels: "positive", "negative", "neutral"
            label: str = result["label"].lower()
            score: float = float(result["score"])
        except Exception as exc:
            log.warning("FinBERT scoring failed for '%s': %s", title[:60], exc)
            label, score = "neutral", 0.5

        scored.append(NewsHeadline(
            title=title,
            link=h.get("link", ""),
            published=h.get("published", ""),
            source=h.get("source", ""),
            sentiment_label=label,
            sentiment_score=score,
        ))

    return scored


def compute_sentiment_percentages(headlines: list[NewsHeadline]) -> dict:
    """
    Compute positive/negative/neutral breakdown as percentages.

    Returns a dict with keys ``positive_pct``, ``negative_pct``, ``neutral_pct``
    (each a float rounded to 1 dp, summing to 100).  Keeps this business logic
    out of the route handler so the route stays thin.
    """
    n = len(headlines)
    if n == 0:
        return {"positive_pct": 0.0, "negative_pct": 0.0, "neutral_pct": 100.0}
    pos_pct = sum(1 for h in headlines if h.sentiment_label == "positive") / n * 100
    neg_pct = sum(1 for h in headlines if h.sentiment_label == "negative") / n * 100
    neu_pct = 100 - pos_pct - neg_pct
    return {
        "positive_pct": round(pos_pct, 1),
        "negative_pct": round(neg_pct, 1),
        "neutral_pct":  round(neu_pct, 1),
    }


def aggregate_sentiment(headlines: list[NewsHeadline]) -> str:
    """
    Return "Bullish", "Neutral", or "Bearish" from weighted sentiment scores.

    Weight = model confidence score. Positive score sum vs negative score sum
    drives the aggregate; neutral breaks the tie toward "Neutral".
    """
    if not headlines:
        return "Neutral"

    pos_weight = sum(h.sentiment_score for h in headlines if h.sentiment_label == "positive")
    neg_weight = sum(h.sentiment_score for h in headlines if h.sentiment_label == "negative")
    total = pos_weight + neg_weight

    if total == 0:
        return "Neutral"

    # More than 10pp difference in weighted share → directional label
    pos_share = pos_weight / total
    if pos_share >= 0.55:
        return "Bullish"
    elif pos_share <= 0.45:
        return "Bearish"
    return "Neutral"


def load_cached_sentiment(cache_path: Path) -> NewsSentimentResult | None:
    """
    Read latest.json. Return None if missing or older than 12 hours.
    """
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        # Ensure timezone-aware comparison
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(tz=timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours > _CACHE_MAX_AGE_HOURS:
            return None

        headlines = [NewsHeadline(**h) for h in data["headlines"]]
        return NewsSentimentResult(
            headlines=headlines,
            aggregate=data["aggregate"],
            positive_pct=data["positive_pct"],
            negative_pct=data["negative_pct"],
            neutral_pct=data["neutral_pct"],
            fetched_at=data["fetched_at"],
            n_sources=data["n_sources"],
        )
    except Exception as exc:
        log.warning("Failed to load news cache: %s", exc)
        return None


def save_sentiment_cache(result: NewsSentimentResult, cache_path: Path) -> None:
    """Serialise NewsSentimentResult to JSON at cache_path."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
