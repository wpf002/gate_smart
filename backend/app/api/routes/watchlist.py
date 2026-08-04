"""
Watchlist API — per-user follows of horses, trainers, and jockeys, plus a
matcher that surfaces which followed entities are entered in the upcoming cards.

All routes require an authenticated user (JWT). Owners are unsupported (no owner
field in the NA feed).
"""
import re

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select

from app.core import database as _db
from app.core.auth import user_id_from_request
from app.models.watchlist import WATCHLIST_ENTITY_TYPES, WatchlistItem

router = APIRouter()


def normalize_entity(name: str) -> str:
    """Match key: lowercased with all punctuation dropped and whitespace
    collapsed, so feed spelling variants resolve to the same entity.

    This matters because sources disagree: the search index returns
    "Irad Ortiz Jr" while racecards carry "Irad Ortiz, Jr.". Without stripping
    commas/periods those become different keys, and a follow made from search
    would silently never match a race (so no alert would ever fire).
    """
    # Apostrophes/periods are intra-word and are dropped outright ("O'Brien" ->
    # "obrien", "Jr." -> "jr"); every other separator becomes a space.
    lowered = re.sub(r"['’.]", "", (name or "").lower())
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def build_watchlist_matches(items: list, cards_by_day: dict) -> list[dict]:
    """Pure matcher: given the user's watchlist items (each with .entity_type,
    .entity_key, .entity_label) and cards keyed by day
    ({"today": [racecard, ...], "tomorrow": [...]}), return one entry per
    (followed entity, race) it appears in. No DB or network — unit-testable.
    """
    if not items:
        return []
    watched: dict[str, dict[str, str]] = {t: {} for t in WATCHLIST_ENTITY_TYPES}
    for it in items:
        if it.entity_type in watched:
            watched[it.entity_type][it.entity_key] = it.entity_label

    matches: list[dict] = []
    seen: set[tuple] = set()
    for day, cards in cards_by_day.items():
        for race in cards or []:
            race_meta = {
                "race_id": race.get("race_id"),
                "course": race.get("course") or race.get("track_code"),
                "race_name": race.get("race_name") or race.get("title"),
                "off_dt": race.get("off_dt"),
                "post_time_et": race.get("post_time_et"),
                "day": day,
            }
            for r in race.get("runners", []):
                if r.get("scratched") or r.get("non_runner"):
                    continue
                horse = r.get("horse_name") or r.get("horse") or ""
                candidates = [
                    ("horse", normalize_entity(str(r.get("horse_id") or ""))),
                    ("horse", normalize_entity(horse)),
                    ("trainer", normalize_entity(r.get("trainer") or "")),
                    ("jockey", normalize_entity(r.get("jockey") or "")),
                ]
                for etype, key in candidates:
                    if key and key in watched[etype]:
                        dedup = (etype, watched[etype][key], race_meta["race_id"])
                        if dedup in seen:
                            continue
                        seen.add(dedup)
                        matches.append({
                            **race_meta,
                            "entity_type": etype,
                            "entity_label": watched[etype][key],
                            "horse_name": horse,
                            "number": r.get("number") or r.get("cloth_number"),
                            "jockey": r.get("jockey"),
                            "trainer": r.get("trainer"),
                        })
    matches.sort(key=lambda m: (m.get("off_dt") or "9999"))
    return matches


class AddItem(msgspec.Struct):
    entity_type: str
    entity_label: str
    entity_key: str | None = None  # server derives from label when omitted


def _require_user(request: Request) -> int:
    uid = user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail="Sign in to use your watchlist")
    return uid


def _item_json(item: WatchlistItem) -> dict:
    return {
        "id": item.id,
        "entity_type": item.entity_type,
        "entity_key": item.entity_key,
        "entity_label": item.entity_label,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("")
async def list_watchlist(request: Request) -> JSONResponse:
    uid = _require_user(request)
    async with _db._AsyncSessionLocal() as db:
        rows = await db.execute(
            select(WatchlistItem).where(WatchlistItem.user_id == uid)
            .order_by(WatchlistItem.entity_type, WatchlistItem.entity_label)
        )
        items = list(rows.scalars().all())
    return JSONResponse({"items": [_item_json(i) for i in items], "total": len(items)})


@router.post("")
async def add_watchlist(request: Request) -> JSONResponse:
    uid = _require_user(request)
    try:
        req = msgspec.json.decode(await request.body(), type=AddItem)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    etype = (req.entity_type or "").lower().strip()
    if etype not in WATCHLIST_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {WATCHLIST_ENTITY_TYPES}")
    label = (req.entity_label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="entity_label is required")
    key = normalize_entity(req.entity_key or label)
    if not key:
        raise HTTPException(status_code=400, detail="entity_key/label did not normalize to anything")

    async with _db._AsyncSessionLocal() as db:
        # Idempotent add — return the existing row if already followed.
        existing = await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == uid,
                WatchlistItem.entity_type == etype,
                WatchlistItem.entity_key == key,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = WatchlistItem(user_id=uid, entity_type=etype, entity_key=key[:160], entity_label=label[:200])
            db.add(row)
            await db.commit()
            await db.refresh(row)
    return JSONResponse(_item_json(row), status_code=201)


@router.delete("/{item_id}")
async def remove_watchlist(item_id: int, request: Request) -> JSONResponse:
    uid = _require_user(request)
    async with _db._AsyncSessionLocal() as db:
        # Scoped to the caller — a user can only delete their own rows.
        result = await db.execute(
            delete(WatchlistItem).where(
                WatchlistItem.id == item_id, WatchlistItem.user_id == uid
            )
        )
        await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse({"deleted": item_id})


@router.get("/today")
async def watchlist_today(request: Request) -> JSONResponse:
    """Followed entities entered in today's or tomorrow's cards.

    Matches each runner's horse / trainer / jockey (normalized) against the
    user's watchlist and returns one entry per (followed entity, race).
    """
    uid = _require_user(request)
    from app.services.racing_api import get_na_racecards_full

    async with _db._AsyncSessionLocal() as db:
        rows = await db.execute(select(WatchlistItem).where(WatchlistItem.user_id == uid))
        items = list(rows.scalars().all())
    if not items:
        return JSONResponse({"matches": [], "total": 0})

    cards_by_day = {}
    for day in ("today", "tomorrow"):
        try:
            data = await get_na_racecards_full(day)
            cards_by_day[day] = data.get("racecards", [])
        except Exception:
            cards_by_day[day] = []

    matches = build_watchlist_matches(items, cards_by_day)
    return JSONResponse({"matches": matches, "total": len(matches)})
