"""Post-pull sanity report for data/cache/bloomberg_v2/. Run on the Mac after copying data from FRTL.

Usage:
    PYTHONPATH=. python scripts/verify_v2_cache.py
"""
from __future__ import annotations
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "data" / "cache" / "bloomberg_v2"


def main() -> None:
    meta = V2 / "meta"
    manifest_path = meta / "universe_v2.json"
    if not manifest_path.exists():
        print("universe_v2.json not found — run --discover first.")
        return

    manifest = json.loads(manifest_path.read_text())
    print(f"Universe manifest: {len(manifest)} tickers")

    for sub in ["equities", "indices", "commodities", "macro"]:
        subdir = V2 / sub
        files = sorted(subdir.glob("*.parquet")) if subdir.exists() else []
        print(f"\n== {sub}: {len(files)} files ==")
        if not files:
            continue
        spans: list[tuple] = []
        field_cov: dict[str, int] = {}
        for f in files:
            df = pd.read_parquet(f)
            if not df.empty:
                spans.append((f.stem, df.index.min(), df.index.max(), len(df)))
                for c in df.columns:
                    field_cov[c] = field_cov.get(c, 0) + 1
        if spans:
            spans.sort(key=lambda x: x[1])
            print(f"  earliest start: {spans[0][0]} @ {spans[0][1].date()}")
            print(f"  latest   start: {spans[-1][0]} @ {spans[-1][1].date()}")
            print(f"  field coverage: {field_cov}")

    safe = lambda t: t.replace(" ", "_")
    missing = [t for t in manifest if not (V2 / "equities" / f"{safe(t)}.parquet").exists()]
    print(f"\nMissing equities vs manifest: {len(missing)}")
    for t in missing[:40]:
        print(f"  - {t}")
    if len(missing) > 40:
        print(f"  ... and {len(missing) - 40} more")

    failed = meta / "failed_v2.json"
    if failed.exists():
        log = json.loads(failed.read_text())
        print(f"\nFailure log: {len(log)} entries")
        sample = dict(list(log.items())[:10])
        print(json.dumps(sample, indent=2))
    else:
        print("\nNo failure log (good).")

    sectors_path = meta / "sectors_v2.json"
    if sectors_path.exists():
        sectors = json.loads(sectors_path.read_text())
        print(f"\nSectors: {len(sectors)} entries in sectors_v2.json")
    else:
        print("\nsectors_v2.json not found (run --sectors).")


if __name__ == "__main__":
    main()
