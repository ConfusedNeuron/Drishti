"""
Market shock events study — drawdown episode detection over NIFTY 50 with sector cross-section.

Usage:
    DRISHTI_DATA_VERSION=v2 PYTHONPATH=. python scripts/build_events_study.py

Writes: data/cache/research_artifacts_v2/events_study.json
Requires: v2 bloomberg cache (indices/ folder with NIFTY Index parquet)
"""
from __future__ import annotations
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── v2 guard ──────────────────────────────────────────────────────────────────

def _require_v2() -> None:
    import os
    if os.environ.get("DRISHTI_DATA_VERSION") != "v2":
        print("ERROR: Set DRISHTI_DATA_VERSION=v2 before running this script.")
        print("  DRISHTI_DATA_VERSION=v2 PYTHONPATH=. python scripts/build_events_study.py")
        sys.exit(1)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_index_px(ticker: str, cache_dir: Path) -> pd.Series | None:
    """Load PX_LAST for one index parquet from the v2 indices folder."""
    fname = ticker.replace(" ", "_") + ".parquet"
    p = cache_dir / "indices" / fname
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "PX_LAST" not in df.columns:
        return None
    s = df["PX_LAST"].dropna()
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


# ── public build function (importable by tests) ───────────────────────────────

def build_events_study(
    nifty_px: pd.Series,
    sector_px: pd.DataFrame,
    labels: list[dict],
    threshold: float = 0.10,
) -> dict:
    """Core study builder — pure function, no I/O.

    Parameters
    ----------
    nifty_px   : NIFTY 50 price series
    sector_px  : sector index price DataFrame (one column per sector)
    labels     : event label dicts from event_labels.json
    threshold  : minimum drawdown depth to qualify as an episode

    Returns
    -------
    JSON-safe dict ready to write as events_study.json
    """
    from src.research.events import detect_drawdown_episodes, match_labels, episode_stats, statistical_levels
    from src.dashboard.json_safe import clean_json

    episodes = detect_drawdown_episodes(nifty_px, threshold=threshold)
    episodes = match_labels(episodes, labels)

    episode_records = []
    for e in episodes:
        stats = episode_stats(e, sector_px) if not sector_px.empty else {}
        record = {
            "label": e.get("label", "Unlabeled episode"),
            "cause": e.get("cause", "unknown"),
            "peak_date": e["peak_date"].isoformat() if hasattr(e["peak_date"], "isoformat") else str(e["peak_date"]),
            "trough_date": e["trough_date"].isoformat() if hasattr(e["trough_date"], "isoformat") else str(e["trough_date"]),
            "recovery_date": (
                e["recovery_date"].isoformat()
                if e["recovery_date"] is not None and hasattr(e["recovery_date"], "isoformat")
                else (str(e["recovery_date"]) if e["recovery_date"] is not None else None)
            ),
            "depth": round(e["depth"], 4),
            "fall_days": e["fall_days"],
            "recovery_days": e["recovery_days"],
            **stats,
        }
        episode_records.append(record)

    levels = statistical_levels(episodes)

    return clean_json({
        "as_of": date.today().isoformat(),
        "threshold": threshold,
        "n_episodes": len(episodes),
        "statistical_levels": levels,
        "episodes": episode_records,
    })


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _require_v2()

    from src.config import ARTIFACTS_DIR, DATA_DIR, MAPPINGS_DIR

    cache_dir = DATA_DIR / "cache" / "bloomberg_v2"

    # ── Load NIFTY 50 ──────────────────────────────────────────────────────────
    nifty_px = _load_index_px("NIFTY_Index", cache_dir)
    if nifty_px is None:
        # Try alternate naming conventions
        for candidate in ["NIFTY Index", "NSENIFTY Index"]:
            nifty_px = _load_index_px(candidate, cache_dir)
            if nifty_px is not None:
                break

    if nifty_px is None or nifty_px.empty:
        print("ERROR: NIFTY index price series not found in v2 cache.")
        print(f"  Expected: {cache_dir / 'indices' / 'NIFTY_Index.parquet'}")
        print("  Run: DRISHTI_DATA_VERSION=v2 PYTHONPATH=. python scripts/pull_drishti_v2.py")
        sys.exit(1)

    print(f"NIFTY: {len(nifty_px)} rows  ({nifty_px.index[0].date()} → {nifty_px.index[-1].date()})")

    # ── Load sector indices ────────────────────────────────────────────────────
    from src.config import SECTOR_TICKERS
    sector_series: dict[str, pd.Series] = {}
    for name, ticker in SECTOR_TICKERS.items():
        s = _load_index_px(ticker, cache_dir)
        if s is not None and not s.empty:
            sector_series[name] = s

    sector_px = pd.DataFrame(sector_series) if sector_series else pd.DataFrame()
    print(f"Sector indices loaded: {list(sector_px.columns)}")

    # ── Load event labels ──────────────────────────────────────────────────────
    labels_path = MAPPINGS_DIR / "event_labels.json"
    if not labels_path.exists():
        print(f"ERROR: {labels_path} not found.")
        sys.exit(1)
    labels = json.loads(labels_path.read_text())
    print(f"Event labels: {len(labels)} curated windows loaded")

    # ── Build study ────────────────────────────────────────────────────────────
    art = build_events_study(nifty_px, sector_px, labels, threshold=0.10)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / "events_study.json"
    out.write_text(json.dumps(art, indent=2))
    print(f"Wrote {out}")
    print(f"  {art['n_episodes']} episodes detected")
    for ep in art["episodes"]:
        depth_pct = round(ep["depth"] * 100, 1)
        print(f"  [{ep['peak_date']} → {ep['trough_date']}]  {ep['label']}  depth={depth_pct}%")


if __name__ == "__main__":
    main()
