from datetime import date

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.cache import cache_incr

router = APIRouter()


class ClickRequest(msgspec.Struct):
    affiliate_id: str
    session_id: str
    race_id: str = ""


@router.post("/click")
async def log_click(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=ClickRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    today = date.today().isoformat()
    await cache_incr(f"affiliate:clicks:{req.affiliate_id}:{today}", ttl=86400)
    return JSONResponse({"logged": True})
