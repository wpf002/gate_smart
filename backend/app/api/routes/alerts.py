from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.cache import cache_get, cache_keys

router = APIRouter()


class AlertCheck(msgspec.Struct):
    race_id: str
    horses: list[dict]   # list of { horse_id, horse_name, current_odds }


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

    return JSONResponse({
        "race_id": req.race_id,
        "alerts": alerts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })


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
