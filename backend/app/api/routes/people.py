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
    # v2: horses are now "entered AND winning", which turns over every day, so
    # the key carries the date and the payload can't outlive the card.
    import datetime

    cache_key = f"people:suggestions:v2:{datetime.date.today().isoformat()}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    from sqlalchemy import text as _text

    from app.core import database as _db

    if not _db._AsyncSessionLocal:
        return JSONResponse({"horses": [], "trainers": [], "jockeys": []})

    async def _top(column: str, days: int, min_wins: int = 0, limit: int = SUGGEST_LIMIT):
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
                sql, {"since": since, "min_wins": min_wins, "limit": limit}
            )).all()
        return [{"name": r.name, "wins": int(r.wins or 0),
                 "last_run": r.last_run.isoformat() if r.last_run else None}
                for r in rows if r.name]

    async def _entered_horses() -> set[str]:
        """Horses actually entered in today's or tomorrow's cards, lowercased.

        Horse search only covers live entries, so suggesting the archive's
        winningest names sent people to "no horses found" for any of them not
        running this week. The suggestions are now the intersection: in-form
        horses you can actually open.
        """
        names: set[str] = set()
        for day in ("today", "tomorrow"):
            try:
                data = await racing_api.get_na_racecards_full(day)
            except Exception:
                continue
            for race in data.get("racecards", []) or []:
                for r in race.get("runners", []) or []:
                    if r.get("scratched") or r.get("non_runner"):
                        continue
                    n = (r.get("horse_name") or "").strip().lower()
                    if n:
                        names.add(n)
        return names

    async def _in_form_runners(names: set[str]):
        """Of the horses entered, the ones winning most lately."""
        if not names:
            return []
        since = datetime.date.today() - datetime.timedelta(days=SUGGEST_HORSE_WINDOW_DAYS)
        sql = _text("""
            SELECT horse_name AS name,
                   COUNT(*) FILTER (WHERE finish_pos = 1) AS wins,
                   MAX(race_date) AS last_run
            FROM horse_form_lines
            WHERE lower(horse_name) = ANY(:names) AND race_date >= :since
            GROUP BY horse_name
            HAVING COUNT(*) FILTER (WHERE finish_pos = 1) >= 1
            ORDER BY wins DESC, last_run DESC
            LIMIT :limit
        """)
        async with _db._AsyncSessionLocal() as db:
            rows = (await db.execute(sql, {"names": list(names), "since": since,
                                           "limit": SUGGEST_LIMIT})).all()
        return [{"name": r.name, "wins": int(r.wins or 0),
                 "last_run": r.last_run.isoformat() if r.last_run else None}
                for r in rows if r.name]

    try:
        payload = {
            "horses": await _in_form_runners(await _entered_horses()),
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
PROFILE_RECENT_LIMIT = 12
PROFILE_TRACK_LIMIT = 8


def _person_columns(person_type: str) -> tuple[str, str]:
    """(form-archive column, chart/PP name prefix) for a person type."""
    return ("trainer", "trainer") if person_type == "trainer" else ("jockey", "jockey")


@router.get("/profile")
async def person_profile(name: str = "", type: str = "trainer") -> JSONResponse:
    """One trainer or jockey, read from every archive that can speak for them.

    Two windows, the same four measures on each, so the cards compare:
    everything before this year, and this year.

    Which archives feed which:

      jockeys   past performances (2012+, `pp_jockey_*` is the rider in that
                run — it agrees with the authoritative 2023 chart on 94% of the
                266,841 runs in both), plus charts and form lines.
      trainers  charts (2023) and form lines (2024+) only. Past performances
                has no per-run trainer column; its `trainer_*` sits in the card
                block beside the card-level `jockey_*`, which agrees with the
                chart just 45% of the time. Trainers look better at 82% only
                because trainers rarely change, so crediting those runs would
                quietly misattribute the ones that did.

    No age and no career start: the feed's person endpoints are not on our plan
    (404 and 401), and nothing on file carries a birth date. "First on file" is
    the date our records begin, which is not when the career did, and the page
    says so in those words.
    """
    person_type = (type or "").lower().strip()
    if person_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {_VALID_TYPES}")
    full = (name or "").strip()
    if len(full) < 2:
        raise HTTPException(status_code=400, detail="name must be at least 2 characters")

    # v3: two comparable windows, and jockeys reach back to 2012.
    cache_key = f"people:profile:v3:{person_type}:{full.lower()}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    import datetime

    from sqlalchemy import text as _text

    from app.core import database as _db

    if not _db._AsyncSessionLocal:
        raise HTTPException(status_code=503, detail="Database unavailable")

    col, prefix = _person_columns(person_type)
    key = full.lower()
    year_start = datetime.date(datetime.date.today().year, 1, 1)
    chart_name = f"lower({prefix}_first || ' ' || {prefix}_last)"
    is_jockey = person_type == "jockey"

    async def _one(sql: str, **params):
        async with _db._AsyncSessionLocal() as db:
            return (await db.execute(_text(sql), {"key": key, **params})).first()

    async def _all(sql: str, **params):
        async with _db._AsyncSessionLocal() as db:
            return (await db.execute(_text(sql), {"key": key, **params})).all()

    try:
        # 2023, every runner on file — the only window with a real denominator.
        chart_q = _one(f"""
            SELECT COUNT(*) AS starts,
                   COUNT(*) FILTER (WHERE official_finish = 1) AS wins,
                   COUNT(*) FILTER (WHERE official_finish <= 3) AS itm,
                   COUNT(DISTINCT horse_name_key) AS horses,
                   COUNT(DISTINCT track_code) AS tracks,
                   MIN(race_date) AS first_run
            FROM horse_result_charts
            WHERE {chart_name} = :key
        """)
        # Form lines, split either side of January 1.
        prior_form_q = _one(f"""
            SELECT COUNT(*) FILTER (WHERE finish_pos = 1) AS wins,
                   COUNT(*) AS itm,
                   COUNT(DISTINCT track) AS tracks,
                   COUNT(DISTINCT horse_name) AS horses,
                   MIN(race_date) AS first_run
            FROM horse_form_lines
            WHERE lower({col}) = :key AND race_date < :year_start
        """, year_start=year_start)
        season_q = _one(f"""
            SELECT COUNT(*) FILTER (WHERE finish_pos = 1) AS wins,
                   COUNT(*) AS itm,
                   COUNT(DISTINCT track) AS tracks,
                   COUNT(DISTINCT horse_name) AS horses,
                   MAX(race_date) AS last_run
            FROM horse_form_lines
            WHERE lower({col}) = :key AND race_date >= :year_start
        """, year_start=year_start)
        # Jockeys only: the rides the charts and form lines never saw.
        pp_q = _one("""
            SELECT COUNT(*) AS starts,
                   COUNT(*) FILTER (WHERE official_finish = 1) AS wins,
                   COUNT(*) FILTER (WHERE official_finish <= 3) AS itm,
                   COUNT(DISTINCT horse_name_key) AS horses,
                   COUNT(DISTINCT pp_track_code) AS tracks,
                   MIN(pp_race_date) AS first_run
            FROM horse_past_performances
            WHERE lower(pp_jockey_first || ' ' || pp_jockey_last) = :key
              AND pp_race_date < '2023-01-01'
        """) if is_jockey else None
        tracks_q = _all(f"""
            SELECT track, COUNT(*) FILTER (WHERE finish_pos = 1) AS wins, COUNT(*) AS itm
            FROM horse_form_lines
            WHERE lower({col}) = :key
            GROUP BY track ORDER BY wins DESC, itm DESC LIMIT :tracks
        """, tracks=PROFILE_TRACK_LIMIT)
        surfaces_q = _all(f"""
            SELECT surface, COUNT(*) FILTER (WHERE finish_pos = 1) AS wins
            FROM horse_form_lines
            WHERE lower({col}) = :key AND surface IS NOT NULL AND surface <> ''
            GROUP BY surface HAVING COUNT(*) FILTER (WHERE finish_pos = 1) > 0
            ORDER BY wins DESC LIMIT 6
        """)
        winners_q = _all(f"""
            SELECT horse_name, track, race_date, win_payoff
            FROM horse_form_lines
            WHERE lower({col}) = :key AND finish_pos = 1
            ORDER BY race_date DESC LIMIT :limit
        """, limit=PROFILE_RECENT_LIMIT)

        queries = [chart_q, prior_form_q, season_q, tracks_q, surfaces_q, winners_q]
        if pp_q is not None:
            queries.append(pp_q)
        results = await asyncio.gather(*queries)
        chart, prior_form, season, tracks, surfaces, winners = results[:6]
        pp = results[6] if pp_q is not None else None
    except Exception as e:  # noqa: BLE001
        print(f"[people] profile failed for {person_type} {full!r}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Could not build that profile")

    def _n(row, field):
        return int(getattr(row, field, 0) or 0) if row else 0

    prior_wins = _n(pp, "wins") + _n(chart, "wins") + _n(prior_form, "wins")
    prior_itm = _n(pp, "itm") + _n(chart, "itm") + _n(prior_form, "itm")
    if not prior_wins and not _n(season, "itm") and not prior_itm:
        raise HTTPException(status_code=404, detail=f"No record for {full}")

    firsts = [getattr(r, "first_run", None) for r in (pp, chart, prior_form) if r]
    firsts = [str(d) for d in firsts if d]
    # Tracks and horses can't be summed across archives without double counting
    # the same track or horse, so each window reports the widest single archive
    # rather than a total that would be too high.
    prior = {
        "wins": prior_wins,
        "itm": prior_itm,
        # distinct counts don't add up across archives; take the largest seen
        "tracks": max(_n(pp, "tracks"), _n(chart, "tracks"), _n(prior_form, "tracks")),
        "horses": max(_n(pp, "horses"), _n(chart, "horses"), _n(prior_form, "horses")),
        "first_run": min(firsts) if firsts else None,
        # 2023 is the one season with losing runs on file, so its rate is the
        # only one that can be quoted, and it's labelled as that season alone.
        "rated_season": 2023 if _n(chart, "starts") else None,
        "rated_starts": _n(chart, "starts"),
        "rated_wins": _n(chart, "wins"),
        "rated_win_rate": (round(_n(chart, "wins") / _n(chart, "starts"), 4)
                           if _n(chart, "starts") else None),
    }
    payload = {
        "name": full,
        "type": person_type,
        "entity_key": normalize_entity(full),
        "season": datetime.date.today().year,
        "prior": prior,
        "current": {
            "wins": _n(season, "wins"),
            "itm": _n(season, "itm"),
            "tracks": _n(season, "tracks"),
            "horses": _n(season, "horses"),
            "last_run": season.last_run.isoformat() if season and season.last_run else None,
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
