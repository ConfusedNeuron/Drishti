"""v2 universe: manifest loading, large/mid buckets, equal-weight sector composites."""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

V2_META = DATA_DIR / "cache" / "bloomberg_v2" / "meta"


def load_universe() -> dict:
    p = V2_META / "universe_v2.json"
    return json.loads(p.read_text()) if p.exists() else {}


def load_sectors() -> dict[str, str]:
    p = V2_META / "sectors_v2.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text())
    return {
        t: (rec.get("GICS_SECTOR_NAME") or rec.get("INDUSTRY_SECTOR") or "Unknown")
        for t, rec in raw.items()
    }


def build_size_buckets(manifest: dict) -> dict[str, list[str]]:
    """Classify tickers as large (NSE100) or mid (everything else)."""
    large, mid = [], []
    for t, rec in manifest.items():
        if "NSE100 Index" in rec.get("indices", []):
            large.append(t)
        else:
            mid.append(t)
    return {"large": sorted(large), "mid": sorted(mid)}


def sector_composites(
    returns_df: pd.DataFrame,
    sectors: dict[str, str],
    bucket: list[str] | None = None,
) -> pd.DataFrame:
    """Equal-weight mean daily return per sector.
    NaN-aware: a stock contributes only on days it traded (mean over available names)."""
    cols = [c for c in returns_df.columns if bucket is None or c in bucket]
    by_sector: dict[str, list[str]] = {}
    for c in cols:
        sector = sectors.get(c, "Unknown")
        by_sector.setdefault(sector, []).append(c)
    out = {
        s: returns_df[members].mean(axis=1)
        for s, members in by_sector.items()
        if len(members) >= 2
    }
    return pd.DataFrame(out).dropna(how="all") if out else pd.DataFrame()


def load_v2_returns(tickers: list[str], min_days: int | None = None) -> pd.DataFrame:
    """Read PX_LAST for tickers from bloomberg_v2/equities, NaN-aligned (outer join),
    pct_change per column independently — no cross-sectional dropna truncation."""
    from src.risk.returns import filter_min_history
    from src.config import MIN_HISTORY_DAYS

    base = DATA_DIR / "cache" / "bloomberg_v2" / "equities"
    series = {}
    for t in tickers:
        p = base / f"{t.replace(' ', '_')}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            if "PX_LAST" in df.columns:
                series[t] = df["PX_LAST"]
    if not series:
        return pd.DataFrame()

    px = pd.DataFrame(series)
    px.index = pd.to_datetime(px.index)
    px = filter_min_history(px.sort_index(), min_days or MIN_HISTORY_DAYS)
    return px.pct_change()
