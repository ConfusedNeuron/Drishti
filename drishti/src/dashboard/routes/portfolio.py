from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from src.portfolio.importer import load_sample, load_csv, load_zerodha
from src.models import PortfolioSnapshot
import dataclasses, json

router = APIRouter()

# In-memory session snapshot
_current_snapshot: PortfolioSnapshot | None = None


def _snap_to_dict(snap: PortfolioSnapshot) -> dict:
    return dataclasses.asdict(snap)


@router.post("/import/sample")
async def import_sample(sample_id: str = "nifty-demo-2026"):
    global _current_snapshot
    try:
        _current_snapshot = load_sample(sample_id)
        return _snap_to_dict(_current_snapshot)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...)):
    global _current_snapshot
    content = await file.read()
    try:
        _current_snapshot = load_csv(content)
        return _snap_to_dict(_current_snapshot)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/import/zerodha")
async def import_zerodha(api_key: str, access_token: str):
    global _current_snapshot
    try:
        _current_snapshot = load_zerodha(access_token, api_key)
        return _snap_to_dict(_current_snapshot)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/current")
async def get_current():
    if _current_snapshot is None:
        raise HTTPException(status_code=404, detail="No portfolio loaded. Use /import/sample first.")
    return _snap_to_dict(_current_snapshot)


def get_snapshot() -> PortfolioSnapshot:
    """Dependency helper for other routes."""
    if _current_snapshot is None:
        raise HTTPException(status_code=400, detail="No portfolio loaded.")
    return _current_snapshot
