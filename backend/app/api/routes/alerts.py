import asyncio
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.cache import cache_get, cache_keys, cache_set, cache_delete
from app.services.notifications import send_value_alert_notification

router = APIRouter()


class AlertCheck(msgspec.Struct):
    race_id: str
    horses: list[dict]   # list of { horse_id, horse_name, current_odds }


class SubscribeRequest(msgspec.Struct):
    race_id: str
    session_id: str
    onesignal_player_id: str


class ValueAlert(msgspec.Struct):
    horse_id: str
    horse_name: str
    fair_odds: str
    fair_decimal: float
    current_odds: str
    current_decimal: float
    value_gap: float
    value_percent: float
    alert_level: str   # "strong" | "moderate" | "watch"


def _parse_decimal(odds: str) -> Optional[float]:
    if not odds or odds in ("?", "SP"):
        return None
    if "/" in str(odds):
        try:
            n, d = str(odds).split("/")
            return int(n) / int(d) + 1
        except (ValueError, ZeroDivisionError):
            return None
    try:
        v = float(odds)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


@router.post("/check")
async def check_alerts(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AlertCheck)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    alerts = []
    for horse in req.horses:
        horse_id = horse.get("horse_id", "")
        horse_name = horse.get("horse_name", "")
        current_odds = horse.get("current_odds", "")

        if not horse_id:
            continue

        stored = await cache_get(f"alerts:fair:{req.race_id}:{horse_id}")
        if not stored:
            continue

        fair_decimal = stored.get("fair_decimal")
        if not fair_decimal:
            continue

        current_decimal = _parse_decimal(current_odds)
        if not current_decimal:
            continue

        value_gap = current_decimal - fair_decimal
        value_percent = (value_gap / fair_decimal) * 100

        if value_percent <= 5:
            continue

        if value_percent > 30:
            alert_level = "strong"
        elif value_percent > 15:
            alert_level = "moderate"
        else:
            alert_level = "watch"

        alerts.append({
            "horse_id": horse_id,
            "horse_name": horse_name or stored.get("horse_name", ""),
            "fair_odds": stored.get("fair_odds_fractional", ""),
            "fair_decimal": fair_decimal,
            "current_odds": current_odds,
            "current_decimal": round(current_decimal, 2),
            "value_gap": round(value_gap, 2),
            "value_percent": round(value_percent, 1),
            "alert_level": alert_level,
        })

    alerts.sort(key=lambda a: a["value_percent"], reverse=True)

    # Fire push notification for the top strong/moderate alert
    top = next((a for a in alerts if a["alert_level"] in ("strong", "moderate")), None)
    if top:
        sub_keys = await cache_keys(f"sub:{req.race_id}:*")
        player_ids = []
        for k in sub_keys:
            sub = await cache_get(k)
            if sub and sub.get("onesignal_player_id"):
                player_ids.append(sub["onesignal_player_id"])
        if player_ids:
            asyncio.create_task(send_value_alert_notification(
                horse_name=top["horse_name"],
                race_name=req.race_id,
                course="",
                current_odds=top["current_odds"],
                fair_odds=top["fair_odds"],
                value_percent=top["value_percent"],
                alert_level=top["alert_level"],
                external_user_ids=player_ids,
            ))

    return JSONResponse({
        "race_id": req.race_id,
        "alerts": alerts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })


@router.post("/subscribe")
async def subscribe_alerts(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=SubscribeRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    key = f"sub:{req.race_id}:{req.session_id}"
    await cache_set(key, {
        "onesignal_player_id": req.onesignal_player_id,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
        "race_id": req.race_id,
        "session_id": req.session_id,
    }, ex=86400)
    return JSONResponse({"subscribed": True})


@router.delete("/subscribe/{race_id}")
async def unsubscribe_alerts(race_id: str, request: Request) -> JSONResponse:
    session_id = request.headers.get("X-Session-ID", "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    await cache_delete(f"sub:{race_id}:{session_id}")
    return JSONResponse({"unsubscribed": True})



@router.get("/race/{race_id}")
async def race_fair_prices(race_id: str) -> JSONResponse:
    """Return all stored fair prices for a race."""
    keys = await cache_keys(f"alerts:fair:{race_id}:*")
    prices = []
    for key in keys:
        data = await cache_get(key)
        if data:
            # Append horse_id extracted from key
            horse_id = key.split(":")[-1]
            prices.append({"horse_id": horse_id, **data})
    return JSONResponse({"race_id": race_id, "fair_prices": prices})
