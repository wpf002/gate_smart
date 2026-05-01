"""
The Racing API client — Standard plan.
Endpoint docs: https://api.theracingapi.com
Rate limit: 5 req/sec. Redis caching keeps us well within this.
"""
import httpx
from fastapi import HTTPException

from app.core.cache import cache_get, cache_set
from app.core.config import settings

BASE_URL = "https://api.theracingapi.com/v1"


def _auth() -> tuple[str, str]:
    return (settings.RACING_API_USERNAME, settings.RACING_API_PASSWORD)


async def _get(
    path: str,
    params: dict = None,
    cache_key: str = None,
    ttl: int = 300,
) -> dict:
    if cache_key:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}{path}",
            params=params,
            auth=_auth(),
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Racing API error: {resp.status_code}",
        )

    data = resp.json()

    if cache_key:
        await cache_set(cache_key, data, ex=ttl)

    return data


def _best_odds(odds_list: list) -> str:
    """Extract the best available price from the bookmaker odds array.
    API keys: fractional, decimal (not odds_fraction/odds_decimal).
    """
    if not odds_list:
        return "SP"
    try:
        # Exclude exchange entries which have non-standard fractional values
        bm = [o for o in odds_list if o.get("ew_places")]
        if not bm:
            bm = odds_list
        best = max(bm, key=lambda o: float(o.get("decimal") or o.get("odds_decimal") or 0))
        return best.get("fractional") or best.get("odds_fraction") or str(best.get("decimal", "SP"))
    except Exception:
        return "SP"


def _normalize_runner(r: dict) -> dict:
    """Map Standard-tier runner fields to consistent frontend names."""
    return {
        **r,
        "horse_name": r.get("horse") or r.get("horse_name", ""),
        "cloth_number": r.get("number") or r.get("cloth_number"),
        "stall_number": r.get("draw") or r.get("stall_number"),
        "official_rating": r.get("ofr") or r.get("official_rating"),
        "rpr": r.get("rpr"),
        "ts": r.get("ts"),            # Timeform speed figure
        "weight": r.get("lbs"),
        "odds": _best_odds(r.get("odds", [])),
        "odds_list": r.get("odds", []),  # full bookmaker list
        "form": r.get("form", ""),
        "silk_url": r.get("silk_url"),
        "spotlight": r.get("spotlight", ""),
        "comment": r.get("comment", ""),
        "trainer_14_days": r.get("trainer_14_days"),
    }


def _normalize_race(r: dict) -> dict:
    """Map Standard-tier race fields to consistent frontend names."""
    distance = r.get("distance") or (
        f"{r['distance_f']}f" if r.get("distance_f") else None
    )
    return {
        **r,
        "time": r.get("off_time") or r.get("time", ""),
        "title": r.get("race_name") or r.get("title", ""),
        "distance": distance,
        "going_detail": r.get("going_detailed") or r.get("going"),
        "runners": [_normalize_runner(runner) for runner in r.get("runners", [])],
    }


# ── Racecards ─────────────────────────────────────────────────────────────────

async def get_racecards(date: str = None, region: str = None) -> dict:
    """Standard plan: /racecards/standard accepts day=today|tomorrow.

    Always fetches and caches the full card (all regions) to avoid redundant
    API calls. Region filtering is applied in-memory after the cache read.
    Region codes match the API's own field values: GB, IRE, USA, CAN, AUS, etc.
    Multiple regions can be passed comma-separated, e.g. "USA,CAN".
    """
    if date and date not in ("today", "tomorrow"):
        return {"racecards": [], "total": 0}

    day_key = date or "today"

    raw = await _get(
        "/racecards/standard",
        params={"day": day_key},
        cache_key=f"racecards:all:{day_key}",
        ttl=600,
    )
    races = [_normalize_race(r) for r in raw.get("racecards", [])]

    if region:
        codes = {r.strip().upper() for r in region.split(",")}
        races = [r for r in races if r.get("region", "").upper() in codes]

    return {"racecards": races, "total": len(races)}


async def get_race(race_id: str) -> dict:
    """Find a NA race by ID. Format: '{MEET_ID}-{race_number}', e.g. 'IND_1775520000000-1'."""
    if "-" in race_id:
        meet_id = race_id.rsplit("-", 1)[0]
        try:
            entries_data = await get_na_meet_entries(meet_id)
            meet_info = {k: v for k, v in entries_data.items() if k != "races"}
            for race in entries_data.get("races", []):
                normalized = _normalize_na_race(race, meet_info)
                if normalized.get("race_id") == race_id:
                    return normalized
        except Exception:
            pass

    raise HTTPException(status_code=404, detail="Race not found")


# ── Results ───────────────────────────────────────────────────────────────────

def _normalize_result_runner(r: dict) -> dict:
    return {
        **r,
        "horse_name": r.get("horse") or r.get("horse_name", ""),
        "odds": r.get("sp") or "SP",
        "position": r.get("position"),
    }


def _normalize_result(r: dict) -> dict:
    return {
        **r,
        "time": r.get("off") or r.get("time", ""),
        "title": r.get("race_name") or r.get("title", ""),
        "distance": r.get("dist") or r.get("distance"),
        "runners": [_normalize_result_runner(rn) for rn in r.get("runners", [])],
    }


async def get_results(date: str = None, region: str = None) -> dict:
    """Results endpoint: /results/today or /results/YYYY-MM-DD."""
    path = f"/results/{date}" if date and date != "today" else "/results/today"
    params = {}
    if region:
        params["region"] = region

    raw = await _get(
        path,
        params=params or None,
        cache_key=f"results:{region or 'all'}:{date or 'today'}",
        ttl=1800,
    )
    results = [_normalize_result(r) for r in raw.get("results", [])]
    return {"results": results, "total": len(results)}


# ── Horses ────────────────────────────────────────────────────────────────────

async def search_horses(name: str) -> dict:
    """Search horses by name (Standard plan)."""
    if not name or len(name.strip()) < 2:
        return {"horses": [], "total": 0}

    try:
        data = await _get(
            "/horses/search",
            params={"name": name.strip()},
            cache_key=f"horse_search:{name.strip().lower()}",
            ttl=3600,
        )
        return data
    except HTTPException:
        # Fallback to local racecard search if API search fails
        return {"horses": [], "total": 0, "source": "api_failed"}


async def get_horse(horse_id: str) -> dict:
    """Horse profile — not available on Standard. Search racecard data."""
    raise HTTPException(
        status_code=404,
        detail="Individual horse profiles require a Pro plan. Use search to find horses in upcoming races.",
    )


async def get_horse_results(horse_id: str, limit: int = 10) -> dict:
    raise HTTPException(
        status_code=402,
        detail="Horse past results require a Pro plan",
    )


# ── Jockeys & Trainers ────────────────────────────────────────────────────────

async def get_na_meets(date: str = None) -> dict:
    """Get all North America race meets for a given date (requires NA add-on)."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    eastern = ZoneInfo("America/New_York")
    if not date or date == "today":
        race_date = datetime.now(eastern).date().isoformat()
    elif date == "tomorrow":
        race_date = (datetime.now(eastern).date() + timedelta(days=1)).isoformat()
    else:
        race_date = date
    return await _get(
        "/north-america/meets",
        params={"start_date": race_date, "end_date": race_date},
        cache_key=f"na:meets:{race_date}",
        ttl=600,
    )


async def get_na_meet_entries(meet_id: str) -> dict:
    """Get all horse entries for a North America meet."""
    return await _get(
        f"/north-america/meets/{meet_id}/entries",
        cache_key=f"na:entries:{meet_id}",
        ttl=600,
    )


async def get_na_meet_results(meet_id: str) -> dict:
    """Get results for a North America meet."""
    return await _get(
        f"/north-america/meets/{meet_id}/results",
        cache_key=f"na:results:{meet_id}",
        ttl=3600,
    )


def _parse_na_distance_furlongs(description: str, dist_value=None, dist_unit: str = "") -> float | None:
    """
    Parse NA distance description to decimal furlongs, handling mixed fractions.
    "5 1/2 Furlongs" → 5.5    "1 1/16 Miles"  → 8.5    "6 Furlongs"    → 6.0
    "1 Mile"         → 8.0    "300 Yards"      → ~1.36
    Falls back to dist_value + dist_unit if description can't be parsed.
    """
    import re
    from fractions import Fraction
    if description:
        desc = description.strip()
        # Handle "X Miles Y Yards" (e.g. "1 Mile 70 Yards")
        m2 = re.match(
            r'^(\d+)(?:\s+(\d+)/(\d+))?\s+miles?\s+(\d+)\s+yards?$',
            desc, re.IGNORECASE,
        )
        if m2:
            whole = int(m2.group(1))
            frac = Fraction(int(m2.group(2)), int(m2.group(3))) if m2.group(2) else Fraction(0)
            yards = int(m2.group(4))
            return float((Fraction(whole) + frac) * 8 + Fraction(yards, 220))
        # Handle "X [Furlongs|Miles|Yards]" with optional fraction
        m = re.match(
            r'^(\d+)(?:\s+(\d+)/(\d+))?\s+(furlong|mile|yard)s?$',
            desc, re.IGNORECASE,
        )
        if m:
            whole = int(m.group(1))
            frac = Fraction(int(m.group(2)), int(m.group(3))) if m.group(2) else Fraction(0)
            total = Fraction(whole) + frac
            unit = m.group(4).lower()
            if unit == "furlong":
                return float(total)
            if unit == "mile":
                return float(total * 8)
            if unit == "yard":
                return float(total / 220)
    # Fallback: integer distance_value (loses fractions but better than nothing)
    if dist_value is not None:
        try:
            v = float(dist_value)
            u = (dist_unit or "").upper()
            if u == "F":
                return v
            if u == "M":
                return v * 8
            if u == "Y":
                return v / 220
        except (TypeError, ValueError):
            pass
    return None


def _normalize_na_race(race: dict, meet: dict) -> dict:
    """Normalize a NA race entry to match GateSmart's internal race schema."""
    from datetime import datetime, timezone as tz

    # race_key is an object like {"race_number": "1", "day_evening": "D"}
    race_key = race.get("race_key") or {}
    race_number = race_key.get("race_number", "") if isinstance(race_key, dict) else ""
    race_id = f"{meet.get('meet_id', '')}-{race_number}" if race_number else meet.get("meet_id", "")

    # post_time_long is Unix milliseconds; convert to ISO-8601
    post_time_long = race.get("post_time_long")
    off_dt = ""
    if post_time_long:
        try:
            off_dt = datetime.fromtimestamp(int(post_time_long) / 1000, tz=tz.utc).isoformat()
        except Exception:
            pass

    # Distance in furlongs — parse description for fractional accuracy
    # e.g. "5 1/2 Furlongs" → 5.5, "1 1/16 Miles" → 8.5, "300 Yards" → 1.36
    distance_f = _parse_na_distance_furlongs(
        race.get("distance_description", ""),
        race.get("distance_value"),
        race.get("distance_unit", ""),
    )

    runners = []
    for entry in race.get("runners", []):
        jockey = entry.get("jockey") or {}
        trainer = entry.get("trainer") or {}
        if isinstance(jockey, dict):
            first_last = f"{jockey.get('first_name', '')} {jockey.get('last_name', '')}".strip()
            jockey_name = first_last or jockey.get("alias", "")
        else:
            jockey_name = str(jockey)

        if isinstance(trainer, dict):
            first_last = f"{trainer.get('first_name', '')} {trainer.get('last_name', '')}".strip()
            trainer_name = first_last or trainer.get("alias", "")
        else:
            trainer_name = str(trainer)

        scratch_indicator = entry.get("scratch_indicator", "")
        is_scratched = scratch_indicator and scratch_indicator.lower() not in ("", "n", "no")
        finish_pos = (
            entry.get("finish_position")
            or entry.get("official_finish")
            or entry.get("position")
        )
        runners.append({
            "horse_id": str(entry.get("registration_number", "")),
            "horse_name": entry.get("horse_name", ""),
            "horse": entry.get("horse_name", ""),
            "jockey": jockey_name,
            "trainer": trainer_name,
            "program_number": str(entry.get("program_number", "")),
            "number": str(entry.get("program_number", "")),
            "cloth_number": str(entry.get("program_number", "")),
            "age": "",
            "sex": "",
            "weight": entry.get("weight", ""),
            "form": "",
            "odds": entry.get("morning_line_odds", ""),
            "sp": entry.get("morning_line_odds", ""),
            "official_rating": None,
            "non_runner": is_scratched,
            "scratched": is_scratched,
            "status": "scratched" if is_scratched else "",
            "claiming_price": entry.get("claiming_price"),
            "finish_position": finish_pos,
            "position": finish_pos,
        })

    return {
        "race_id": race_id,
        "course": race.get("track_name") or meet.get("track_name", ""),
        "course_id": meet.get("track_id", ""),
        "date": meet.get("date", ""),
        "time": race.get("post_time", ""),
        "off_time": race.get("post_time", ""),
        "off_dt": off_dt,
        "title": race.get("race_name", ""),
        "race_name": race.get("race_name", ""),
        "distance": race.get("distance_description", ""),
        "distance_f": distance_f,
        "surface": race.get("surface_description", ""),
        "going": race.get("track_condition", ""),
        "prize": race.get("purse"),
        "race_class": race.get("race_class", ""),
        "race_type": (
            race.get("race_type_description") or
            race.get("race_type") or
            race.get("race_class") or
            race.get("type") or
            race.get("race_class_description") or
            race.get("conditions_abbrev") or
            ""
        ),
        "pattern": race.get("grade", ""),
        "region": "usa",
        "runners": runners,
        "field_size": len(runners),
    }


async def get_na_racecards_full(date: str = None) -> dict:
    """
    Fetch all NA meets for a date and expand each with full entries.
    Returns a unified structure matching the standard racecards format.

    Note: get_na_meet_entries returns ALL entries for a meet (which can span
    multiple days). We filter by post_time_long so we only return races whose
    scheduled post time falls on the requested date (UTC calendar day).
    """
    from datetime import date as date_cls, timedelta, datetime, timezone as tz
    from zoneinfo import ZoneInfo
    eastern = ZoneInfo("America/New_York")

    meets_data = await get_na_meets(date)
    meets = meets_data.get("meets", [])

    # Determine the target date in US Eastern Time — all NA races are US-based.
    # Using UTC here causes the "today" window to roll over at 8 PM ET in summer,
    # making evening races disappear and tomorrow's card appear prematurely.
    if not date or date == "today":
        target_date = datetime.now(eastern).date()
    elif date == "tomorrow":
        target_date = datetime.now(eastern).date() + timedelta(days=1)
    else:
        try:
            target_date = date_cls.fromisoformat(date)
        except Exception:
            target_date = datetime.now(eastern).date()

    # Build millisecond window covering the full ET calendar day.
    # ET midnight to ET midnight ensures evening races (post midnight UTC) are included.
    et_day_start = datetime(target_date.year, target_date.month, target_date.day,
                            tzinfo=eastern)
    et_day_end = et_day_start + timedelta(days=1)
    day_start_ms = int(et_day_start.timestamp() * 1000)
    day_end_ms = int(et_day_end.timestamp() * 1000)

    import re as _re
    _WAGER_POOL = _re.compile(
        r'\b(pick\s*\d+|trifecta|superfecta|exacta|daily\s*double|rolling\s*pick|over\s*[/-]?\s*under)\b',
        _re.IGNORECASE,
    )

    all_races = []
    seen_race_ids: set[str] = set()
    for meet in meets:
        meet_id = meet.get("meet_id", "")
        if not meet_id:
            continue
        # Skip Over/Under prop-bet pools — meet_id prefix "OMA_" signals these
        # sportsbook-style wagers (race_name='Over/Under', field_size=2). They're
        # not real races and should not appear on the racecard list.
        if meet_id.startswith("OMA_"):
            continue
        # Skip exotic wager pool "meets" — they duplicate individual race entries.
        # Check all string fields on the meet object (name, track_name, meet_id, etc.)
        # because the API stores the wager name in different fields depending on pool type.
        meet_text = " ".join(str(v) for v in meet.values() if isinstance(v, str))
        if _WAGER_POOL.search(meet_text):
            continue
        try:
            entries_data = await get_na_meet_entries(meet_id)
            races = entries_data.get("races", [])
            # entries_data carries track_name, track_id, date, meet_id
            meet_info = {k: v for k, v in entries_data.items() if k != "races"}
            for race in races:
                # Skip races whose post time is not on the target date
                ptl = race.get("post_time_long")
                if ptl:
                    try:
                        if not (day_start_ms <= int(ptl) < day_end_ms):
                            continue
                    except (TypeError, ValueError):
                        pass
                normalized = _normalize_na_race(race, meet_info)
                # Deduplicate by race_id in case the same race appears in multiple meets
                rid = normalized.get("race_id", "")
                if rid and rid in seen_race_ids:
                    continue
                if rid:
                    seen_race_ids.add(rid)
                all_races.append(normalized)
        except Exception:
            continue

    return {"racecards": all_races, "total": len(all_races), "region": "usa"}


async def get_na_results_full(date: str = None) -> dict:
    """
    Fetch all NA meet results for a date, unified into a results list.

    The NA results endpoint returns races with a `runners` array containing
    only the top-3 finishers in finish order (no explicit position field).
    Runner keys differ entirely from the entries endpoint — this function
    builds the result dict from scratch rather than reusing _normalize_na_race.
    """
    meets_data = await get_na_meets(date)
    meets = meets_data.get("meets", [])

    all_results = []
    for meet in meets:
        meet_id = meet.get("meet_id", "")
        if not meet_id:
            continue
        try:
            results_data = await get_na_meet_results(meet_id)
            races = results_data.get("races", [])
            for race in races:
                # Build race_id using the same formula as _normalize_na_race
                # so IDs match what was stored at prediction time.
                race_key = race.get("race_key") or {}
                race_number = (
                    race_key.get("race_number", "")
                    if isinstance(race_key, dict)
                    else ""
                )
                race_id = f"{meet_id}-{race_number}" if race_number else meet_id

                # Results API: runners array is in finish order (index 0 = winner).
                # No position field exists — derive it from array index.
                raw_runners = race.get("runners", [])
                runners = []
                for idx, r in enumerate(raw_runners):
                    pos = idx + 1
                    runners.append({
                        "horse_name": r.get("horse_name", ""),
                        "horse": r.get("horse_name", ""),
                        "position": pos,
                        "finish_position": pos,
                        "program_number": str(r.get("program_number", "")),
                        "number": str(r.get("program_number", "")),
                        "win_payoff": r.get("win_payoff"),
                        "place_payoff": r.get("place_payoff"),
                        "show_payoff": r.get("show_payoff"),
                        "sp": r.get("win_payoff"),
                    })

                all_results.append({
                    "race_id": race_id,
                    "race_name": race.get("race_name", ""),
                    "track_name": race.get("track_name") or meet.get("track_name", ""),
                    "race_type": (
                        race.get("race_type_description") or
                        race.get("race_type") or
                        race.get("race_class") or
                        race.get("type") or
                        race.get("race_class_description") or
                        ""
                    ),
                    "surface": race.get("surface_description") or race.get("surface", ""),
                    "runners": runners,
                })
        except Exception:
            continue

    return {"results": all_results, "total": len(all_results)}


async def search_jockeys(name: str) -> dict:
    return await _get(
        "/jockeys/search",
        params={"name": name},
        cache_key=f"jockey_search:{name.lower()}",
        ttl=3600,
    )


async def search_trainers(name: str) -> dict:
    return await _get(
        "/trainers/search",
        params={"name": name},
        cache_key=f"trainer_search:{name.lower()}",
        ttl=3600,
    )


async def get_jockey(jockey_id: str) -> dict:
    raise HTTPException(status_code=402, detail="Jockey profile requires Pro plan")


async def get_trainer(trainer_id: str) -> dict:
    raise HTTPException(status_code=402, detail="Trainer profile requires Pro plan")
