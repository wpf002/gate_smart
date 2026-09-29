"""
People search — find trainers and jockeys by name so they can be followed.

Combines two sources:
  1. The Racing API /trainers/search + /jockeys/search (broad, includes NA).
  2. A scan of today's/tomorrow's NA racecards, so anyone actually entered is
     findable even when upstream search misses them — and we can flag who is
     racing now, which is what a watchlist user cares about.
Results are deduped by normalized name (same key the watchlist matches on).
"""
import asyncio
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


# ── Trainer / jockey profile ─────────────────────────────────────────────────

# Three archives, three different shapes, and the good one isn't the recent one:
#
#   horse_result_charts       2023 only, EVERY runner (42,618 races, fields to
#                             18th) — the only table with a real start count,
#                             so the only place a win rate can come from.
#   horse_past_performances   2012-06 onward, per-horse PP lines carrying speed
#                             and pace figures, class ratings and odds.
#   horse_form_lines          2024 onward, top-three finishes only. Wins are
#                             real; starts are not, because a loss was never
#                             written down.
#
# A profile reads all three and labels which window each number came from. It
# never divides a 2024+ win count by anything.
PROFILE_RECENT_LIMIT = 8


def _person_columns(person_type: str) -> tuple[str, str]:
    """(form-archive column, chart/PP name prefix) for a person type."""
    return ("trainer", "trainer") if person_type == "trainer" else ("jockey", "jockey")


@router.get("/profile")
async def person_profile(name: str = "", type: str = "trainer") -> JSONResponse:
    """Everything the three archives know about one trainer or jockey."""
    person_type = (type or "").lower().strip()
    if person_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {_VALID_TYPES}")
    full = (name or "").strip()
    if len(full) < 2:
        raise HTTPException(status_code=400, detail="name must be at least 2 characters")

    cache_key = f"people:profile:v1:{person_type}:{full.lower()}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    from sqlalchemy import text as _text

    from app.core import database as _db

    if not _db._AsyncSessionLocal:
        raise HTTPException(status_code=503, detail="Database unavailable")

    col, prefix = _person_columns(person_type)
    key = full.lower()
    chart_name = f"lower({prefix}_first || ' ' || {prefix}_last)"

    async def _one(sql: str, **params):
        async with _db._AsyncSessionLocal() as db:
            return (await db.execute(_text(sql), {"key": key, **params})).first()

    async def _all(sql: str, **params):
        async with _db._AsyncSessionLocal() as db:
            return (await db.execute(_text(sql), {"key": key, **params})).all()

    # Five independent reads: gathered, not awaited one after another. Serially
    # this was five round trips and the page waited for all of them end to end.
    try:
        # 2023: the only window with losing runs on file, so the only honest rate.
        rated_q = _one(f"""
            SELECT COUNT(*) AS starts,
                   COUNT(*) FILTER (WHERE official_finish = 1) AS wins,
                   COUNT(*) FILTER (WHERE official_finish <= 3) AS itm,
                   COUNT(DISTINCT horse_name_key) AS horses
            FROM horse_result_charts
            WHERE {chart_name} = :key
        """)
        # 2024 onward: wins are real, starts were never recorded.
        recent_q = _one(f"""
            SELECT COUNT(*) FILTER (WHERE finish_pos = 1) AS wins,
                   COUNT(*) AS itm,
                   COUNT(DISTINCT track) AS tracks,
                   COUNT(DISTINCT horse_name) AS horses,
                   MIN(race_date) AS first_line, MAX(race_date) AS last_line
            FROM horse_form_lines
            WHERE lower({col}) = :key
        """)
        tracks_q = _all(f"""
            SELECT track, COUNT(*) FILTER (WHERE finish_pos = 1) AS wins, COUNT(*) AS itm
            FROM horse_form_lines
            WHERE lower({col}) = :key
            GROUP BY track ORDER BY wins DESC, itm DESC LIMIT 5
        """)
        surfaces_q = _all(f"""
            SELECT surface, COUNT(*) FILTER (WHERE finish_pos = 1) AS wins
            FROM horse_form_lines
            WHERE lower({col}) = :key AND surface IS NOT NULL AND surface <> ''
            GROUP BY surface HAVING COUNT(*) FILTER (WHERE finish_pos = 1) > 0
            ORDER BY wins DESC LIMIT 4
        """)
        winners_q = _all(f"""
            SELECT horse_name, track, race_date, win_payoff
            FROM horse_form_lines
            WHERE lower({col}) = :key AND finish_pos = 1
            ORDER BY race_date DESC LIMIT :limit
        """, limit=PROFILE_RECENT_LIMIT)
        rated, recent, tracks, surfaces, winners = await asyncio.gather(
            rated_q, recent_q, tracks_q, surfaces_q, winners_q)
    except Exception as e:  # noqa: BLE001
        print(f"[people] profile failed for {person_type} {full!r}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Could not build that profile")

    if not (rated and rated.starts) and not (recent and recent.itm):
        raise HTTPException(status_code=404, detail=f"No record for {full}")

    starts = int(rated.starts or 0) if rated else 0
    wins_2023 = int(rated.wins or 0) if rated else 0
    payload = {
        "name": full,
        "type": person_type,
        "entity_key": normalize_entity(full),
        # The rate window, stated as its own thing so it can never be read as
        # a career figure or mixed with the 2024+ counts.
        "rated": {
            "season": 2023,
            "starts": starts,
            "wins": wins_2023,
            "itm": int(rated.itm or 0) if rated else 0,
            "horses": int(rated.horses or 0) if rated else 0,
            "win_rate": round(wins_2023 / starts, 4) if starts else None,
            "itm_rate": round(int(rated.itm or 0) / starts, 4) if starts else None,
        } if starts else None,
        "recent": {
            "since": recent.first_line.isoformat() if recent and recent.first_line else None,
            "last_run": recent.last_line.isoformat() if recent and recent.last_line else None,
            "wins": int(recent.wins or 0) if recent else 0,
            "itm": int(recent.itm or 0) if recent else 0,
            "tracks": int(recent.tracks or 0) if recent else 0,
            "horses": int(recent.horses or 0) if recent else 0,
        },
        "top_tracks": [{"track": r.track, "wins": int(r.wins or 0), "itm": int(r.itm or 0)}
                       for r in tracks if r.track],
        "surfaces": [{"surface": r.surface, "wins": int(r.wins or 0)} for r in surfaces],
        "recent_winners": [{"horse": r.horse_name, "track": r.track,
                            "date": r.race_date.isoformat() if r.race_date else None,
                            "win_payoff": float(r.win_payoff) if r.win_payoff else None}
                           for r in winners],
    }
    await cache_set(cache_key, payload, ex=6 * 3600)
    return JSONResponse(payload)
