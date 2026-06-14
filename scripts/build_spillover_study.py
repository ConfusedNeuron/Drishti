"""
Expanded Diebold-Yilmaz spillover study — large/mid/combined panels with IS-OOS split.

Usage:
    PYTHONPATH=. python scripts/build_spillover_study.py

Writes: data/cache/research_artifacts_v2/spillover_study.json
Requires: bloomberg_v2 cache + universe manifest + sectors_v2.json
"""
from __future__ import annotations
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.diebold_yilmaz import compute_spillover, rolling_spillover
from src.dashboard.json_safe import clean_json


def _spillover_to_dict(tbl) -> dict:
    """Convert SpilloverTable to JSON-safe dict."""
    return {
        "total_spillover": tbl.total_spillover,
        "to_spillover": tbl.to_spillover,
        "from_spillover": tbl.from_spillover,
        "net_spillover": tbl.net_spillover,
        "var_lag": tbl.var_lag,
        "fevd_horizon": tbl.fevd_horizon,
    }


def _build_panel(returns_df: pd.DataFrame, train_end: str) -> dict:
    """Compute IS + OOS spillover tables + rolling series for one panel."""
    if returns_df.empty or len(returns_df.columns) < 2:
        return {
            "total_spillover": None,
            "net_spillover": None,
            "in_sample": None,
            "out_of_sample": None,
            "rolling": {},
        }

    is_df = returns_df.loc[:train_end].dropna(how="all")
    oos_df = returns_df.loc[train_end:].dropna(how="all").iloc[1:]  # exclude the train_end row

    def _safe_compute(df: pd.DataFrame):
        if df.empty or len(df) < 50 or len(df.columns) < 2:
            return None
        try:
            return _spillover_to_dict(compute_spillover(df))
        except Exception as e:
            return {"error": str(e)[:200]}

    is_result = _safe_compute(is_df)
    oos_result = _safe_compute(oos_df)

    # Rolling on full window
    rolling_result = {}
    try:
        roll = rolling_spillover(returns_df, window=200, step=21)
        rolling_result = {str(k.date()): float(v) for k, v in roll.items()}
    except Exception:
        pass

    total = is_result.get("total_spillover") if is_result and "error" not in is_result else None
    net = is_result.get("net_spillover") if is_result and "error" not in is_result else None

    return {
        "total_spillover": total,
        "net_spillover": net,
        "in_sample": is_result,
        "out_of_sample": oos_result,
        "rolling": rolling_result,
    }


def build_study(
    large_sectors: pd.DataFrame,
    mid_sectors: pd.DataFrame,
    factors: pd.DataFrame,
    train_end: str = "2023-12-31",
) -> dict:
    """
    Build the spillover study artifact dict.

    Parameters
    ----------
    large_sectors : equal-weight sector composites for Nifty 100 universe
    mid_sectors   : equal-weight sector composites for Midcap 150 universe
    factors       : commodity/macro factor return series
    train_end     : IS/OOS split date (inclusive IS)
    """
    panels = {}

    # Large panel: large sector composites + factors
    if not large_sectors.empty:
        large_combined = pd.concat(
            [df for df in [large_sectors, factors] if not df.empty], axis=1
        ).dropna(how="all")
        panels["large"] = _build_panel(large_combined, train_end)
    else:
        panels["large"] = {"total_spillover": None, "net_spillover": None,
                           "in_sample": None, "out_of_sample": None, "rolling": {}}

    # Mid panel
    if not mid_sectors.empty:
        mid_combined = pd.concat(
            [df for df in [mid_sectors, factors] if not df.empty], axis=1
        ).dropna(how="all")
        panels["mid"] = _build_panel(mid_combined, train_end)
    else:
        panels["mid"] = {"total_spillover": None, "net_spillover": None,
                         "in_sample": None, "out_of_sample": None, "rolling": {}}

    # Combined panel: a genuine whole-universe view. Blend the large- and mid-cap sector
    # composites 50/50 per sector (NaN-aware mean across buckets) rather than dropping the
    # mid duplicates — otherwise "combined" collapses to the large-only panel. A sector
    # present in only one bucket keeps that bucket's series.
    bucket_frames = {k: v for k, v in {"large": large_sectors, "mid": mid_sectors}.items()
                     if not v.empty}
    if bucket_frames:
        blended = pd.concat(bucket_frames, axis=1)             # cols: (bucket, sector)
        # Mean across buckets per sector; transpose-groupby avoids the deprecated axis=1 form.
        combined_sectors = blended.T.groupby(level=1).mean().T
        frames = [df for df in [combined_sectors, factors] if not df.empty]
        combined_df = pd.concat(frames, axis=1).dropna(how="all")
        # Guard only against an accidental sector/factor name collision (keeps the sector).
        combined_df = combined_df.loc[:, ~combined_df.columns.duplicated()]
        panels["combined"] = _build_panel(combined_df, train_end)
    else:
        panels["combined"] = {"total_spillover": None, "net_spillover": None,
                              "in_sample": None, "out_of_sample": None, "rolling": {}}

    return clean_json({
        "as_of": date.today().isoformat(),
        "train_end": train_end,
        "panels": panels,
        "rolling": {
            name: panels[name].get("rolling", {})
            for name in ["large", "mid", "combined"]
        },
    })


def main() -> None:
    from src.research.universe import load_universe, load_sectors, build_size_buckets, sector_composites, load_v2_returns
    from src.risk.returns import load_factor_series
    from src.config import ARTIFACTS_DIR
    from datetime import date as dt

    universe = load_universe()
    if not universe:
        print("ERROR: universe_v2.json not found. Run: python scripts/pull_drishti_v2.py --discover")
        sys.exit(1)

    sectors_map = load_sectors()
    buckets = build_size_buckets(universe)

    print(f"Universe: {len(universe)} tickers, {len(buckets['large'])} large, {len(buckets['mid'])} mid")

    # Load returns
    large_rets = load_v2_returns(buckets["large"])
    mid_rets = load_v2_returns(buckets["mid"])

    print(f"Loaded returns: {large_rets.shape} large, {mid_rets.shape} mid")

    # Build sector composites
    large_sectors = sector_composites(large_rets, sectors_map, bucket=buckets["large"])
    mid_sectors = sector_composites(mid_rets, sectors_map, bucket=buckets["mid"])

    # Factor series from v2 cache
    start_d, end_d = dt(2000, 1, 1), dt.today()
    factors = load_factor_series(["brent", "gold", "copper", "usdinr"], start_d, end_d)

    print(f"Sectors: {large_sectors.shape} large, {mid_sectors.shape} mid")
    print(f"Factors: {factors.shape}")

    art = build_study(large_sectors, mid_sectors, factors, train_end="2023-12-31")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / "spillover_study.json"
    out.write_text(json.dumps(art, indent=2))
    print(f"Wrote {out}")
    for panel_name, p in art["panels"].items():
        ts = p.get("total_spillover")
        print(f"  {panel_name}: total_spillover={ts}")


if __name__ == "__main__":
    main()
