"""Static data endpoint stub — replaced in a later task."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/api/static-data")
async def get_static_data():
    return {"regime": None, "regime_prob": None, "dy_total": None,
            "ic_signals": None, "var_range": None, "data_as_of": None}
