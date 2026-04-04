import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.cache import cache_get, cache_set
from app.core.config import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Structs
# ---------------------------------------------------------------------------

class MapHorseRequest(msgspec.Struct):
    racing_api_horse_id: str
    epc: str
    horse_name: str


class TrackSenseSectional(msgspec.Struct):
    gate_name: str
    gate_distance_furlongs: float
    split_time_ms: int
    speed_kmh: float


class TrackSenseResult(msgspec.Struct):
    finish_position: int
    epc: str
    horse_name: str
    total_time_ms: int
    sectionals: list[TrackSenseSectional]


class TrackSenseWebhookPayload(msgspec.Struct):
    race_id: str
    venue: str
    race_name: str
    distance_furlongs: float
    completed_at: str
    results: list[TrackSenseResult]


# ---------------------------------------------------------------------------
# Part 1 — Horse identity mapping
# ---------------------------------------------------------------------------

@router.post("/map")
async def map_horse(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=MapHorseRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    mapping = {
        "epc": req.epc,
        "horse_name": req.horse_name,
        "mapped_at": datetime.now(timezone.utc).isoformat(),
    }
    await cache_set(f"tracksense:map:{req.racing_api_horse_id}", mapping)

    return JSONResponse({
        "stored": True,
        "racing_api_horse_id": req.racing_api_horse_id,
        "epc": req.epc,
    })


@router.get("/map/{racing_api_horse_id}")
async def get_horse_mapping(racing_api_horse_id: str) -> JSONResponse:
    mapping = await cache_get(f"tracksense:map:{racing_api_horse_id}")
    if mapping is None:
        raise HTTPException(status_code=404, detail="mapping not found")
    return JSONResponse(mapping)


# ---------------------------------------------------------------------------
# Part 2 — Webhook ingestion with HMAC-SHA256 verification
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()

    # DEV BYPASS: if TRACKSENSE_WEBHOOK_SECRET is not configured, skip
    # signature verification so local testing works without a secret.
    # Remove this bypass (or the empty-string branch) before going to production.
    if settings.TRACKSENSE_WEBHOOK_SECRET:
        sig_header = request.headers.get("X-TrackSense-Signature", "")
        if not sig_header.startswith("sha256="):
            return JSONResponse({"error": "invalid signature"}, status_code=401)

        expected = hmac.new(
            settings.TRACKSENSE_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        provided = sig_header[len("sha256="):]
        if not hmac.compare_digest(expected, provided):
            return JSONResponse({"error": "invalid signature"}, status_code=401)

    try:
        payload = msgspec.json.decode(raw_body, type=TrackSenseWebhookPayload)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed webhook payload")

    horses_stored = 0
    for result in payload.results:
        race_entry = {
            "race_id": payload.race_id,
            "venue": payload.venue,
            "race_name": payload.race_name,
            "distance_furlongs": payload.distance_furlongs,
            "completed_at": payload.completed_at,
            "finish_position": result.finish_position,
            "total_time_ms": result.total_time_ms,
            "sectionals": [msgspec.to_builtins(s) for s in result.sectionals],
        }

        redis_key = f"tracksense:sectionals:{result.epc}"
        history = await cache_get(redis_key)
        if history is None:
            history = []

        history.append(race_entry)
        if len(history) > 50:
            history.pop(0)

        await cache_set(redis_key, history)
        horses_stored += 1

    return JSONResponse({"accepted": True, "horses_stored": horses_stored})
