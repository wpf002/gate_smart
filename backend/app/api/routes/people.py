"""
People search — find trainers and jockeys by name so they can be followed.

Combines two sources:
  1. The Racing API /trainers/search + /jockeys/search (broad, includes NA).
  2. A scan of today's/tomorrow's NA racecards, so anyone actually entered is
     findable even when upstream search misses them — and we can flag who is
     racing now, which is what a watchlist user cares about.
Results are deduped by normalized name (same key the watchlist matches on).
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.api.routes.watchlist import normalize_entity
from app.core.cache import cache_get, cache_set
from app.services import racing_api

log = logging.getLogger(__name__)
router = APIRouter()

_VALID_TYPES = ("trainer", "jockey")


async def _upstream_search(person_type: str, q: str) -> list[dict]:
    """Names from The Racing API's own search index."""
    try:
        if person_type == "trainer":
            data = await racing_api.search_trainers(q)
        else:
            data = await racing_api.search_jockeys(q)
    except Exception as e:
        log.info(f"[people] upstream {person_type} search failed: {e}")
        return []
    out = []
    for row in (data or {}).get("search_results", []) or []:
        name = (row.get("name") or "").strip()
        if name:
            out.append({"name": name, "source_id": row.get("id")})
    return out


async def _racecard_people(person_type: str, q_norm: str) -> dict[str, dict]:
    """Matching trainers/jockeys entered in today's or tomorrow's NA cards.

    Returns {normalized_name: {name, racing_today, runner_count}} so the UI can
    show "racing today" next to a result.
    """
    found: dict[str, dict] = {}
    for day in ("today", "tomorrow"):
        try:
            data = await racing_api.get_na_racecards_full(day)
        except Exception:
            continue
        for race in data.get("racecards", []) or []:
            for r in race.get("runners", []) or []:
                if r.get("scratched") or r.get("non_runner"):
                    continue
                name = (r.get(person_type) or "").strip()
                if not name or name.upper() == "SCRATCHED":
                    continue
                key = normalize_entity(name)
                if not key or q_norm not in key:
                    continue
                entry = found.setdefault(
                    key, {"name": name, "racing_today": False, "runner_count": 0}
                )
                entry["runner_count"] += 1
                if day == "today":
                    entry["racing_today"] = True
    return found


@router.get("/search")
async def people_search(q: str = "", type: str = "trainer") -> JSONResponse:
    person_type = (type or "").lower().strip()
    if person_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {_VALID_TYPES}")

    q_stripped = (q or "").strip()
    if len(q_stripped) < 2:
        return JSONResponse({"results": [], "total": 0})
    q_norm = normalize_entity(q_stripped)

    upstream = await _upstream_search(person_type, q_stripped)
    entered = await _racecard_people(person_type, q_norm)

    # Merge: racecard data enriches upstream hits; racecard-only people are added.
    merged: dict[str, dict] = {}
    for row in upstream:
        key = normalize_entity(row["name"])
        if not key:
            continue
        merged[key] = {
            "name": row["name"],
            "entity_key": key,
            "entity_type": person_type,
            "racing_today": False,
            "runner_count": 0,
        }
    for key, info in entered.items():
        if key in merged:
            merged[key]["racing_today"] = info["racing_today"]
            merged[key]["runner_count"] = info["runner_count"]
        else:
            merged[key] = {
                "name": info["name"],
                "entity_key": key,
                "entity_type": person_type,
                "racing_today": info["racing_today"],
                "runner_count": info["runner_count"],
            }

    # People racing today first, then those with entries, then alphabetical.
    results = sorted(
        merged.values(),
        key=lambda r: (not r["racing_today"], -r["runner_count"], r["name"].lower()),
    )[:40]
    return JSONResponse({"results": results, "total": len(results)})


# ── Suggestions for an empty search box ──────────────────────────────────────

SUGGEST_WINDOW_DAYS = 90
SUGGEST_LIMIT = 8
# Horses turn over: a handful of wins takes longer to accumulate than a
# trainer's, and a horse that stopped running in June isn't worth suggesting.
SUGGEST_HORSE_WINDOW_DAYS = 120


@router.get("/suggestions")
async def search_suggestions() -> JSONResponse:
    """Names worth tapping when the search box is empty.

    Everything here is counted from our own form archive rather than a curated
    list of famous people, so it stays true as the meets change and it can't
    quietly go stale. Only wins are shown: the archive stores top-three
    finishes, so a "starts" denominator would be wrong and any rate built on it
    would be a fiction.
    """
    cache_key = f"people:suggestions:v1:{SUGGEST_WINDOW_DAYS}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    import datetime

    from sqlalchemy import text as _text

    from app.core import database as _db

    if not _db._AsyncSessionLocal:
        return JSONResponse({"horses": [], "trainers": [], "jockeys": []})

    async def _top(column: str, days: int, min_wins: int = 0):
        # The cutoff is computed here rather than as CURRENT_DATE - :days:
        # asyncpg can't infer a type for the bound integer in that expression
        # and the comparison comes back as "date >= integer".
        since = datetime.date.today() - datetime.timedelta(days=days)
        sql = _text(f"""
            SELECT {column} AS name,
                   COUNT(*) FILTER (WHERE finish_pos = 1) AS wins,
                   MAX(race_date) AS last_run
            FROM horse_form_lines
            WHERE {column} IS NOT NULL AND {column} <> ''
              AND race_date >= :since
            GROUP BY {column}
            HAVING COUNT(*) FILTER (WHERE finish_pos = 1) >= :min_wins
            ORDER BY wins DESC, last_run DESC
            LIMIT :limit
        """)
        async with _db._AsyncSessionLocal() as db:
            rows = (await db.execute(
                sql, {"since": since, "min_wins": min_wins, "limit": SUGGEST_LIMIT}
            )).all()
        return [{"name": r.name, "wins": int(r.wins or 0),
                 "last_run": r.last_run.isoformat() if r.last_run else None}
                for r in rows if r.name]

    try:
        payload = {
            "horses": await _top("horse_name", SUGGEST_HORSE_WINDOW_DAYS, min_wins=3),
            "trainers": await _top("trainer", SUGGEST_WINDOW_DAYS),
            "jockeys": await _top("jockey", SUGGEST_WINDOW_DAYS),
            "days": SUGGEST_WINDOW_DAYS,
            "horse_days": SUGGEST_HORSE_WINDOW_DAYS,
        }
    except Exception as e:  # noqa: BLE001
        print(f"[people] suggestions failed: {type(e).__name__}: {e}")
        return JSONResponse({"horses": [], "trainers": [], "jockeys": []})

    await cache_set(cache_key, payload, ex=6 * 3600)
    return JSONResponse(payload)
