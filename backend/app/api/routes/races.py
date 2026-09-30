import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.cache import cache_get, cache_incr, cache_set
from app.services import racing_api

router = APIRouter()


async def _settle_predictions(race_ids: list[str]) -> None:
    """Check pending predictions against NA results and update accuracy counters."""
    for race_id in race_ids:
        try:
            pred = await cache_get(f"predictions:{race_id}")
            if not pred or pred.get("status") != "pending":
                continue

            results_data = await racing_api.get_na_results_full()
            race_result = next(
                (r for r in results_data.get("results", []) if r.get("race_id") == race_id),
                None,
            )
            if not race_result:
                continue

            winner = next(
                (r for r in race_result.get("runners", []) if str(r.get("position", "")) == "1"),
                None,
            )
            if not winner:
                continue

            winner_id = winner.get("horse_id", "")
            winner_name = winner.get("horse_name") or winner.get("horse", "")
            correct = winner_id and winner_id == pred.get("top_pick_horse_id")

            pred["status"] = "correct" if correct else "incorrect"
            pred["actual_winner"] = winner_name
            pred["settled_at"] = datetime.now(timezone.utc).isoformat()
            await cache_set(f"predictions:{race_id}", pred, ex=604800)

            await cache_incr("accuracy:total")
            if correct:
                await cache_incr("accuracy:correct")
        except Exception:
            continue


# ── List payloads ────────────────────────────────────────────────────────────
#
# The races list draws a card per race and shows nothing about any individual
# runner — the field size is all it reads, and the race page fetches its own
# race when you open one. Shipping the whole field with the list cost 544 KB for
# a US day and 3 MB for an international one, which is most of why the page felt
# slow before a single card appeared.

_LIST_DROP = {
    "runners", "betting_forecast", "tip", "verdict", "rail_movements",
    "stalls", "going_detailed", "distance_round", "race_status", "raw",
}


def list_card(race: dict) -> dict:
    """One race as the list needs it: everything but the field."""
    card = {k: v for k, v in race.items() if k not in _LIST_DROP}
    # RaceCard reads runners.length first and falls back to this, so the count
    # survives with no runners attached.
    card["no_of_runners"] = (
        race.get("field_size") or len(race.get("runners") or []) or None)
    return card


def list_payload(data: dict) -> dict:
    return {**data, "racecards": [list_card(r) for r in (data.get("racecards") or [])]}


@router.get("/today")
async def races_today(region: str = None):
    try:
        return list_payload(await racing_api.get_na_racecards_full())
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/results/race/{race_id}")
async def results_for_race(race_id: str):
    """Return finishing order for a single NA race. Race IDs use '{meet_id}-{race_number}' format."""
    for attempt in range(2):
        try:
            if "-" in race_id:
                meet_id, race_number = race_id.rsplit("-", 1)
                meet_results = await racing_api.get_na_meet_results(meet_id)
                for race in meet_results.get("races", []):
                    rk = race.get("race_key") or {}
                    rnum = str(rk.get("race_number", "")) if isinstance(rk, dict) else ""
                    if rnum == str(race_number):
                        # NA results endpoint returns runners as the top-3
                        # finishers in finish order, with no explicit position
                        # field. Fall back to (index + 1) so the result card
                        # shows actual finish positions.
                        runners = []
                        for idx, e in enumerate(race.get("runners", [])):
                            explicit = (
                                e.get("official_finish_position")
                                or e.get("finish_position")
                            )
                            position = str(explicit) if explicit else str(idx + 1)
                            runners.append({
                                "horse_id": str(e.get("registration_number", "")),
                                "horse_name": e.get("horse_name", ""),
                                "position": position,
                                "sp": str(e.get("final_odds") or e.get("morning_line_odds", "SP")),
                                "number": str(e.get("program_number", "")),
                            })
                        if runners:
                            return {"race_id": race_id, "title": race.get("race_name", ""), "runners": runners}
        except Exception:
            pass
        if attempt == 0:
            await asyncio.sleep(1)
    raise HTTPException(status_code=404, detail="Results not yet available")


@router.get("/results/today")
async def results_today(request: Request, background_tasks: BackgroundTasks, region: str = None):
    try:
        data = await racing_api.get_na_results_full()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    sid = request.headers.get("X-Session-ID", "").strip()
    race_ids = [r.get("race_id") for r in data.get("results", []) if r.get("race_id")]

    if sid:
        from app.api.routes.simulator import settle_race_bets
        for rid in race_ids:
            background_tasks.add_task(settle_race_bets, sid, rid)

    if race_ids:
        background_tasks.add_task(_settle_predictions, race_ids)

    return data


@router.get("/results/{result_date}")
async def results_by_date(result_date: str, region: str = None):
    try:
        return await racing_api.get_na_results_full(date=result_date)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/date/{race_date}")
async def races_by_date(race_date: str, region: str = None):
    try:
        return list_payload(await racing_api.get_na_racecards_full(date=race_date))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")



# ── International card, grouped by country ───────────────────────────────────
#
# The US view runs off the North America add-on, which is a separate dataset
# and has no notion of anywhere else. This one runs off the core feed —
# UK, Ireland, France and whatever group races are carded elsewhere — and
# groups by country first, then by track within it.
#
# It reads /racecards/pro rather than /racecards/standard. Same races, far more
# per runner: every bookmaker's price and its movement, RPR, topspeed, official
# rating, the spotlight comment, the trainer's last fourteen days.
#
# Races go through _normalize_race, the same normaliser the US view uses, so
# the page renders them with the same RaceCard rather than a second list that
# has to be kept in step with it.
#
# This has to be declared above /{race_id}: FastAPI matches in declaration
# order, so with it below, "international" was read as a race id and every
# request 404'd.

INTERNATIONAL_TTL = 600


def _card(race: dict) -> dict:
    """One international race, normalised, trimmed to what the list draws."""
    return list_card(racing_api._normalize_race(race))


def _fold(cards: list[dict], names: dict[str, str]) -> list[dict]:
    """Races -> countries -> tracks, each sorted the way it will be read."""
    countries: dict[str, dict] = {}
    for race in cards:
        code = (race.get("region") or "").upper()
        if not code:
            continue
        country = countries.setdefault(code, {
            "region_code": code.lower(),
            "region": names.get(code.lower(), code),
            "tracks": {},
        })
        course = (race.get("course") or "Unknown").strip()
        track = country["tracks"].setdefault(course, {
            "course": course,
            "course_id": race.get("course_id"),
            "races": [],
        })
        track["races"].append(_card(race))

    out = []
    for country in countries.values():
        tracks = []
        for track in country["tracks"].values():
            track["races"].sort(key=lambda r: (r.get("off_dt") or "", r.get("time") or ""))
            track["race_count"] = len(track["races"])
            tracks.append(track)
        tracks.sort(key=lambda t: t["course"].lower())
        out.append({
            "region": country["region"],
            "region_code": country["region_code"],
            "tracks": tracks,
            "track_count": len(tracks),
            "race_count": sum(t["race_count"] for t in tracks),
        })
    # Most racing first, so the countries with a full card lead.
    out.sort(key=lambda c: (-c["race_count"], c["region"]))
    return out


@router.get("/international")
async def races_international(date: str = None):
    """Today's or a given day's non-US card, grouped by country then track."""
    import datetime as _dt

    day = (date or "today").strip().lower()
    if day == "today":
        iso = _dt.date.today().isoformat()
    elif day == "tomorrow":
        iso = (_dt.date.today() + _dt.timedelta(days=1)).isoformat()
    else:
        try:
            iso = _dt.date.fromisoformat(day).isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be today, tomorrow or YYYY-MM-DD")

    # v2: the runner list no longer rides along.
    cache_key = f"races:international:v2:{iso}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        cards, regions = await asyncio.gather(
            racing_api.get_racecards_pro(date=iso),
            racing_api.get_course_regions(),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    names = {r.get("region_code"): r.get("region") for r in regions or []}
    countries = _fold(cards.get("racecards") or [], names)
    payload = {
        "date": iso,
        "countries": countries,
        "total": sum(c["race_count"] for c in countries),
    }
    await cache_set(cache_key, payload, ex=INTERNATIONAL_TTL)
    return payload


@router.get("/{race_id}")
async def race_detail(race_id: str):
    try:
        return await racing_api.get_race(race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")
