"""Static data endpoint — pre-computed Bloomberg cache stats, cached in memory."""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter

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

    artifacts = Path(__file__).resolve().parents[3] / "data" / "cache" / "research_artifacts"
    _try_json(artifacts / "hmm_result.json",  result, ["regime", "regime_prob"])
    _try_json(artifacts / "dy_result.json",   result, ["dy_total"])
    _try_json(artifacts / "ic_result.json",   result, ["ic_signals"])
    _try_json(artifacts / "var_range.json",   result, ["var_range"])
    return result


def _try_json(path: Path, result: dict, keys: list[str]) -> None:
    try:
        data = json.loads(path.read_text())
        for k in keys:
            if k in data:
                result[k] = data[k]
    except Exception:
        pass


@router.get("/api/static-data")
async def get_static_data() -> dict:
    return _load()
