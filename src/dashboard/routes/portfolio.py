from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from urllib.parse import quote
from src.portfolio.importer import load_sample, load_csv, load_zerodha
from src.models import PortfolioSnapshot
from src.config import settings
from src.portfolio import kite_auth
from src.dashboard.json_safe import clean_json
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
async def import_zerodha(api_key: str | None = None, access_token: str | None = None):
    global _current_snapshot
    resolved_token = access_token or kite_auth.load_cached_token() or settings.zerodha_access_token
    resolved_key = api_key or settings.zerodha_api_key
    if not resolved_token:
        raise HTTPException(
            status_code=400,
            detail="No Zerodha access token available. Connect via the login flow or set ZERODHA_ACCESS_TOKEN in .env.",
        )
    try:
        _current_snapshot = load_zerodha(resolved_token, resolved_key)
        return _snap_to_dict(_current_snapshot)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class ZerodhaTokenBody(BaseModel):
    request_token: str


@router.get("/zerodha/login")
async def zerodha_login():
    if not settings.zerodha_api_key or not settings.zerodha_api_secret:
        raise HTTPException(status_code=400, detail="ZERODHA_API_KEY / ZERODHA_API_SECRET not set in .env")
    return {"login_url": kite_auth.login_url(settings.zerodha_api_key)}


@router.get("/zerodha/callback")
async def zerodha_callback(request_token: str, status: str = ""):
    global _current_snapshot
    try:
        if not settings.zerodha_api_key or not settings.zerodha_api_secret:
            raise RuntimeError("ZERODHA_API_KEY / ZERODHA_API_SECRET not set in .env")
        token = kite_auth.exchange_token(settings.zerodha_api_key, settings.zerodha_api_secret, request_token)
        kite_auth.save_token(token, cache_dir=kite_auth.TOKEN_DIR)  # re-read TOKEN_DIR at call time (tests monkeypatch it)
        snap = load_zerodha(token, settings.zerodha_api_key)
        _current_snapshot = snap
        return RedirectResponse(url="/?zerodha=connected", status_code=303)
    except Exception as e:
        reason = str(e)[:200]  # never let token material reach the redirect URL
        return RedirectResponse(url=f"/?zerodha=error&reason={quote(reason)}", status_code=303)


@router.post("/zerodha/token")
async def zerodha_token(body: ZerodhaTokenBody):
    global _current_snapshot
    if not settings.zerodha_api_key or not settings.zerodha_api_secret:
        raise HTTPException(status_code=400, detail="ZERODHA_API_KEY / ZERODHA_API_SECRET not set in .env")
    try:
        token = kite_auth.exchange_token(settings.zerodha_api_key, settings.zerodha_api_secret, body.request_token)
        kite_auth.save_token(token, cache_dir=kite_auth.TOKEN_DIR)  # re-read TOKEN_DIR at call time (tests monkeypatch it)
        snap = load_zerodha(token, settings.zerodha_api_key)
        _current_snapshot = snap
        return _snap_to_dict(snap)
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


@router.get("/pnl")
async def get_pnl():
    """Per-holding unrealized P&L (invested vs current market value). Educational/diagnostic only."""
    snap = get_snapshot()

    rows = []
    for h in snap.holdings:
        invested = h.quantity * h.average_price
        pnl = h.market_value - invested
        pnl_pct = pnl / invested if invested != 0 else None
        rows.append({
            "symbol": h.symbol,
            "sector": h.sector,
            "quantity": h.quantity,
            "average_price": h.average_price,
            "last_price": h.last_price,
            "invested": invested,
            "market_value": h.market_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "weight": h.weight,
        })

    rows.sort(key=lambda r: r["market_value"], reverse=True)

    total_invested = sum(r["invested"] for r in rows)
    total_market_value = sum(r["market_value"] for r in rows)
    total_pnl = total_market_value - total_invested
    total_pnl_pct = total_pnl / total_invested if total_invested != 0 else None

    return clean_json({
        "rows": rows,
        "totals": {
            "invested": total_invested,
            "market_value": total_market_value,
            "pnl": total_pnl,
            "pnl_pct": total_pnl_pct,
        },
        "source": snap.source,
        "as_of": snap.as_of,
    })
