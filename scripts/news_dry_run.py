"""
Dry-run for the Drishti news + FinBERT pipeline.

Usage (from repo root):
    PYTHONPATH=. python scripts/news_dry_run.py

Run twice before demo:
  1st run: downloads ProsusAI/finbert (~440 MB), fetches feeds, scores.
  2nd run: skips download, must complete in < 60s.
Exits nonzero if fewer than 10 headlines scored.
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.news import RSS_FEEDS, fetch_headlines, score_headlines

# ---------------------------------------------------------------------------
# 1. Show configured feeds
# ---------------------------------------------------------------------------
print("=== Drishti news dry-run ===\n")
print(f"Configured feeds ({len(RSS_FEEDS)}):")
for feed in RSS_FEEDS:
    print(f"  {feed}")
print()

# ---------------------------------------------------------------------------
# 2. Fetch headlines (network; failed feeds are skipped gracefully)
# ---------------------------------------------------------------------------
t0 = time.time()
print("Fetching headlines...")
raw = fetch_headlines()
fetch_elapsed = time.time() - t0
print(f"  {len(raw)} raw headlines fetched in {fetch_elapsed:.1f}s\n")

# ---------------------------------------------------------------------------
# 3. Score with FinBERT (first call downloads ~440 MB if not cached)
# ---------------------------------------------------------------------------
print("Scoring with ProsusAI/finbert (first call may download ~440 MB)...")
t1 = time.time()
scored = score_headlines(raw)
score_elapsed = time.time() - t1
total_elapsed = time.time() - t0

# ---------------------------------------------------------------------------
# 4. Per-source counts + totals
# ---------------------------------------------------------------------------
source_counts: Counter = Counter(h.source for h in scored)
print(f"\n--- Results ---")
print(f"{'Source':<25}  {'Headlines':>10}")
print("-" * 38)
for source, count in sorted(source_counts.items(), key=lambda x: -x[1]):
    print(f"{source:<25}  {count:>10}")
print("-" * 38)
print(f"{'TOTAL':<25}  {len(scored):>10}")
print()
print(f"Wall time: fetch={fetch_elapsed:.1f}s  score={score_elapsed:.1f}s  total={total_elapsed:.1f}s")

# ---------------------------------------------------------------------------
# 5. Exit nonzero if fewer than 10 headlines scored
# ---------------------------------------------------------------------------
MIN_HEADLINES = 10
if len(scored) < MIN_HEADLINES:
    print(f"\nFAIL: only {len(scored)} headlines scored (minimum {MIN_HEADLINES}).", file=sys.stderr)
    sys.exit(1)

print(f"\nPASS: {len(scored)} headlines scored.")
