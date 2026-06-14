"""Static data endpoint — pre-computed Bloomberg cache stats, cached in memory."""
from __future__ import annotations
import json
from functools import lru_cache
from fastapi import APIRouter
from src.config import ARTIFACTS_DIR

router = APIRouter()


@lru_cache(maxsize=1)
def _load() -> dict:
    result: dict = {
        "regime": None, "regime_prob": None, "dy_total": None,
        "ic_signals": None, "var_range": None, "data_as_of": None,
    }
    try:
        import src.bloomberg.cache as cache_mod
        for p in cache_mod.CACHE_DIR.glob("equities/*.parquet"):
            _, last = cache_mod.get_cached_range(p.stem)
            if last:
                result["data_as_of"] = str(last)
            break
    except Exception:
        pass

    # regime + hmm_prob_high_vol from v2 regime study (NIFTY Index current state)
    try:
        data = json.loads((ARTIFACTS_DIR / "regime_study.json").read_text())
        current = data["indices"]["NIFTY Index"]["current"]
        result["regime"] = current.get("regime")
        result["regime_prob"] = current.get("hmm_prob_high_vol")
    except Exception:
        pass

    # total connectedness from v2 spillover study; prefer in_sample sub-key (same value, but explicit)
    try:
        data = json.loads((ARTIFACTS_DIR / "spillover_study.json").read_text())
        combined = data["panels"]["combined"]
        ts = combined.get("in_sample", {}).get("total_spillover")
        if ts is None:
            ts = combined.get("total_spillover")
        result["dy_total"] = ts
    except Exception:
        pass

    # ic_signals and var_range: no v2 source exists — remain None
    return result


@router.get("/api/static-data")
async def get_static_data() -> dict:
    return _load()
