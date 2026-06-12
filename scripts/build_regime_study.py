"""
Build bull/bear regime study artifact for v2 data.

Usage:
    DRISHTI_DATA_VERSION=v2 PYTHONPATH=. python scripts/build_regime_study.py [--since 2020-01-01]

Writes: data/cache/research_artifacts_v2/regime_study.json
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2020-01-01")
    args = ap.parse_args()

    if os.environ.get("DRISHTI_DATA_VERSION") != "v2":
        print("ERROR: Set DRISHTI_DATA_VERSION=v2 before running.")
        sys.exit(1)

    from src.research.market_regimes import classify_bull_bear, regime_signs, current_state
    from src.config import DATA_DIR, ARTIFACTS_DIR
    from src.dashboard.json_safe import clean_json

    v2_indices = DATA_DIR / "cache" / "bloomberg_v2" / "indices"
    since = args.since

    TARGET_INDICES = {
        "NIFTY Index": "NIFTY_Index",
        "NSE100 Index": "NSE100_Index",
        "NSEMD150 Index": "NSEMD150_Index",
        "NSESMCP Index": "NSESMCP_Index",
    }

    results = {}
    for ticker, filename in TARGET_INDICES.items():
        p = v2_indices / f"{filename}.parquet"
        if not p.exists():
            continue
        import pandas as pd
        df = pd.read_parquet(p)
        if "PX_LAST" not in df.columns:
            continue
        px = df["PX_LAST"].dropna()
        px.index = pd.to_datetime(px.index)
        px = px.loc[since:]
        if len(px) < 100:
            continue

        regimes = classify_bull_bear(px)
        returns = px.pct_change().dropna()
        signs = regime_signs(returns, regimes)
        cs = current_state(px, regimes)

        timeline = [
            {"date": str(d.date()), "regime": r}
            for d, r in regimes.items()
        ]

        results[ticker] = {
            "timeline": timeline,
            "signs": signs,
            "current": cs,
        }
        print(f"  {ticker}: {cs['regime']} regime, drawdown={cs['drawdown_from_peak']:.1%}")

    # Summary
    currently_bear = [t for t, v in results.items() if v["current"]["regime"] == "bear"]
    closest = min(
        (t for t in results if results[t]["current"]["regime"] == "bull"),
        key=lambda t: results[t]["current"].get("pct_to_bear_threshold", 1.0),
        default=None,
    )

    art = clean_json({
        "as_of": date.today().isoformat(),
        "since": since,
        "indices": results,
        "summary": {
            "currently_bear": currently_bear,
            "closest_to_switch": closest,
        },
    })

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / "regime_study.json"
    out.write_text(json.dumps(art, indent=2))
    print(f"Wrote {out} ({len(results)} indices)")


if __name__ == "__main__":
    main()
