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

async def _recent_track_prefixes(days: int = 28) -> set[str]:
    """Roster of track codes that have run in the last `days`, derived from
    stored predictions. A meet_id looks like ``SAR_1783728000000`` and the
    race_id we store is ``SAR_1783728000000-1``, so the code before the first
    underscore is the track prefix.

    This is the set of tracks we consider "in season" and worth probing for
    directly when the upstream /meets listing drops one. It's self-maintaining:
    a track enters the roster the first day it appears in /meets, and falls out
    `days` after its meet ends, so we never probe forever for a closed track.
    """
    from datetime import date as _date
    from datetime import timedelta

    key = f"na:track_roster:{days}"
    cached = await cache_get(key)
    if cached is not None:
        return set(cached)

    prefixes: set[str] = set()
    try:
        from sqlalchemy import text as _text

        from app.core import database as _db
        cutoff = _date.today() - timedelta(days=days)
        async with _db._AsyncSessionLocal() as db:
            rows = await db.execute(
                _text(
                    "SELECT DISTINCT split_part(race_id, '_', 1) AS prefix "
                    "FROM race_predictions "
                    "WHERE race_date >= :cutoff AND race_id LIKE '%\\_%'"
                ),
                {"cutoff": cutoff},
            )
            for r in rows:
                p = (r[0] or "").strip()
                # Skip wager-pool prefixes (e.g. OMA_ over/under pools) and blanks.
                if p and p != "OMA":
                    prefixes.add(p)
    except Exception:
        return set()

    await cache_set(key, list(prefixes), ex=3600)
    return prefixes


async def _recover_missing_na_meets(union: dict, race_date: str) -> None:
    """Recover tracks the upstream /meets listing dropped for `race_date`.

    The listing endpoint intermittently omits individual tracks (observed:
    Saratoga missing on a Saturday while present on the surrounding Thu/Sun).
    But the per-meet /entries endpoint still holds the full card under a
    deterministic meet_id: ``{TRACK}_{UTC-midnight-ms}``. So for every in-season
    track NOT already listed, we construct that meet_id and probe /entries.
    If real races come back, we add the meet; if the track is genuinely dark
    that day, /entries 404s and we negative-cache it to avoid re-probing.

    Only runs for dates within a few days of now — the app only shows
    today/tomorrow, and probing far-off dates would be wasted calls.
    Mutates ``union['meets']`` in place.
    """
    from datetime import date as _date
    from datetime import datetime, timedelta, timezone

    try:
        target = _date.fromisoformat(race_date)
    except Exception:
        return
    today = _date.today()
    if not (today - timedelta(days=2) <= target <= today + timedelta(days=3)):
        return

    # meet_id timestamp is UTC midnight of the race date, in milliseconds.
    utc_midnight_ms = int(
        datetime(target.year, target.month, target.day, tzinfo=timezone.utc).timestamp() * 1000
    )

    present_prefixes = {
        (m.get("meet_id") or "").split("_", 1)[0]
        for m in union.get("meets", []) or []
        if "_" in (m.get("meet_id") or "")
    }

    roster = await _recent_track_prefixes()
    missing = [p for p in roster if p and p not in present_prefixes]
    if not missing:
        return

    for prefix in missing:
        candidate = f"{prefix}_{utc_midnight_ms}"
        neg_key = f"na:probe:neg:{candidate}"
        if await cache_get(neg_key):
            continue  # recently confirmed dark — don't hammer upstream
        try:
            entries = await get_na_meet_entries(candidate)
        except Exception:
            await cache_set(neg_key, 1, ex=1800)
            continue
        races = entries.get("races") if isinstance(entries, dict) else None
        if races:
            # Real card recovered — add it so the entries loop downstream
            # (and its post-time date filter) picks it up like any other meet.
            union["meets"].append({
                "meet_id": candidate,
                "track_name": entries.get("track_name") or prefix,
                "track_id": entries.get("track_id", ""),
                "date": race_date,
                "_recovered_probe": True,
            })
        else:
            await cache_set(neg_key, 1, ex=1800)


async def get_na_meets(date: str = None) -> dict:
    """Get all North America race meets for a given date (requires NA add-on).

    Maintains a sticky union per date — the upstream API drops meets
    from /north-america/meets once their card finishes, which would make
    a finished track silently disappear from the home page mid-afternoon.
    We persist every meet seen for a date in `na:meets:sticky:{date}`
    (24h TTL) and union new fetches with it so a track stays listed
    until the day ends.

    On top of the sticky union, `_recover_missing_na_meets` probes the
    /entries endpoint directly for any in-season track the listing dropped,
    so a track that is actually running never disappears just because the
    upstream /meets listing flaked for that date.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    eastern = ZoneInfo("America/New_York")
    if not date or date == "today":
        race_date = datetime.now(eastern).date().isoformat()
    elif date == "tomorrow":
        race_date = (datetime.now(eastern).date() + timedelta(days=1)).isoformat()
    else:
        race_date = date

    live = await _get(
        "/north-america/meets",
        params={"start_date": race_date, "end_date": race_date},
        cache_key=f"na:meets:{race_date}",
        ttl=600,
    )

    sticky_key = f"na:meets:sticky:{race_date}"
    sticky = await cache_get(sticky_key) or {"meets": []}

    by_id: dict[str, dict] = {}
    for m in sticky.get("meets", []) or []:
        mid = m.get("meet_id")
        if mid:
            by_id[mid] = m
    # Live response wins on conflicts so we get the freshest field for any
    # meet that's still being updated upstream.
    for m in live.get("meets", []) or []:
        mid = m.get("meet_id")
        if mid:
            by_id[mid] = m

    union = {**live, "meets": list(by_id.values())}
    # Fill listing gaps by probing /entries for in-season tracks that are
    # missing. Runs before the sticky write so recovered meets persist for
    # the rest of the day.
    await _recover_missing_na_meets(union, race_date)
    await cache_set(sticky_key, union, ex=86400)
    return union


async def get_na_meet_entries(meet_id: str) -> dict:
    """Get all horse entries for a North America meet."""
    return await _get(
        f"/north-america/meets/{meet_id}/entries",
        cache_key=f"na:entries:{meet_id}",
        ttl=600,
    )


def _na_results_have_finishes(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    for race in data.get("races", []) or []:
        for runner in race.get("runners", []) or []:
            pos = runner.get("official_finish_position") or runner.get("finish_position")
            if pos and str(pos).strip() not in ("", "0"):
                return True
    return False


async def get_na_meet_results(meet_id: str) -> dict:
    """Get results for a North America meet.

    Uses a short TTL when the response has no finish positions yet (results
    feed hasn't synced) so Try Again actually retries instead of returning
    a stale empty payload for the next hour.
    """
    cache_key = f"na:results:{meet_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{BASE_URL}/north-america/meets/{meet_id}/results",
            auth=_auth(),
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Racing API error: {resp.status_code}")

    data = resp.json()
    ttl = 3600 if _na_results_have_finishes(data) else 30
    await cache_set(cache_key, data, ex=ttl)
    return data


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


def _resolve_post_epoch_ms(post_time_long, meet_id: str) -> int | None:
    """Return absolute epoch-milliseconds for a race post time.

    Upstream is inconsistent between meets: some give ``post_time_long`` as a
    full epoch-ms value (e.g. Saratoga, Gulfstream), others give it as
    milliseconds-since-midnight — a within-day offset that must be added to the
    meet's UTC-midnight epoch (e.g. Monmouth Park). The meet's midnight epoch is
    encoded in the meet_id suffix (``MTH_1783728000000`` → 1783728000000).

    A within-day offset is always < 86_400_000 (ms in a day), while a real epoch
    for any modern date is ~1.78e12 — so the two forms are unambiguous. Feeding
    an offset straight into fromtimestamp() would place the race in 1970 and mark
    every such race permanently "finished", which is the bug this prevents.
    Returns None when the value can't be resolved, so callers treat the post time
    as unknown rather than silently wrong.
    """
    if post_time_long is None:
        return None
    try:
        ptl = int(post_time_long)
    except (TypeError, ValueError):
        return None
    if ptl <= 0:
        return None
    if ptl >= 86_400_000:
        return ptl  # already a full epoch-ms timestamp
    # Within-day offset — anchor it to the meet's UTC-midnight epoch.
    try:
        base = int(str(meet_id).split("_", 1)[1])
    except (IndexError, ValueError):
        return None
    if base >= 86_400_000:
        return base + ptl
    return None


def _normalize_na_race(race: dict, meet: dict) -> dict:
    """Normalize a NA race entry to match GateSmart's internal race schema."""
    from datetime import datetime
    from datetime import timezone as tz

    # race_key is an object like {"race_number": "1", "day_evening": "D"}
    race_key = race.get("race_key") or {}
    race_number = race_key.get("race_number", "") if isinstance(race_key, dict) else ""
    race_id = f"{meet.get('meet_id', '')}-{race_number}" if race_number else meet.get("meet_id", "")

    # post_time_long is either full epoch-ms or ms-since-midnight depending on
    # the meet; _resolve_post_epoch_ms normalizes both to an absolute epoch.
    epoch_ms = _resolve_post_epoch_ms(race.get("post_time_long"), meet.get("meet_id", ""))
    off_dt = ""
    if epoch_ms:
        try:
            off_dt = datetime.fromtimestamp(epoch_ms / 1000, tz=tz.utc).isoformat()
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
    from datetime import date as date_cls
    from datetime import datetime, timedelta
    from datetime import timezone as tz
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
    # Match wager-pool "meets" the upstream API mixes into the meets list.
    # `\bdouble\b` catches stakes-day daily-double pools like "Preakness Double"
    # / "Belmont Double" (and the upstream-truncated "Bes Preakness Double") in
    # addition to the generic "Daily Double". No real NA track name contains
    # "double", so this is safe.
    _WAGER_POOL = _re.compile(
        r'\b(pick\s*\d+|trifecta|superfecta|exacta|double|rolling\s*\w+|over\s*[/-]?\s*under|wager|pool)\b',
        _re.IGNORECASE,
    )

    # Recovery: nightly_predict_all writes a RacePrediction row for every
    # NA race at 11 AM ET, so the DB has a complete record of which tracks
    # ran today even after upstream prunes them from /meets and /entries.
    # Bring those back as stubs so the home page reflects every track
    # that actually ran today, not just the ones still upcoming.
    db_recovered_predictions: list = []
    if target_date == datetime.now(eastern).date():
        try:
            from sqlalchemy import select

            from app.core import database as _db
            from app.models.accuracy import RacePrediction

            live_meet_ids = {m.get("meet_id") for m in meets if m.get("meet_id")}
            async with _db._AsyncSessionLocal() as db:
                result = await db.execute(
                    select(RacePrediction)
                    .where(
                        RacePrediction.race_date == target_date,
                        RacePrediction.user_id.is_(None),
                        RacePrediction.analysis_mode == "auto_daily",
                    )
                )
                preds = list(result.scalars().all())

            recovered_meet_ids = set()
            for p in preds:
                if not p.race_id or "-" not in p.race_id:
                    continue
                meet_id = p.race_id.rsplit("-", 1)[0]
                if meet_id and meet_id not in live_meet_ids:
                    recovered_meet_ids.add(meet_id)
                    db_recovered_predictions.append(p)

            for meet_id in recovered_meet_ids:
                meets.append({"meet_id": meet_id, "_recovered_from_db": True})
        except Exception:
            pass

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
        # Check ONLY identifier fields (name, track_name, meet_id), not every string
        # field on the meet object. Joining all values caught legitimate tracks
        # whose metadata mentioned wager sequences (e.g. "Late Pick 4 features
        # Kentucky Oaks") and dropped the entire card. Race-id dedup below catches
        # any wager-pool duplicates that slip through this narrower check.
        meet_text = " ".join(str(meet.get(k, "")) for k in ("meet_name", "name", "track_name", "meet_id"))
        if _WAGER_POOL.search(meet_text):
            continue
        try:
            entries_data = await get_na_meet_entries(meet_id)
            races = entries_data.get("races", [])
            # entries_data carries track_name, track_id, date, meet_id
            meet_info = {k: v for k, v in entries_data.items() if k != "races"}
            for race in races:
                # Skip races whose post time is not on the target date.
                # Resolve first — some meets encode post_time_long as an
                # offset-from-midnight, so a raw int compare would wrongly drop
                # (or keep) them. Unresolvable times fall through and are kept.
                ptl = race.get("post_time_long")
                if ptl:
                    abs_ms = _resolve_post_epoch_ms(ptl, meet_id)
                    if abs_ms is not None and not (day_start_ms <= abs_ms < day_end_ms):
                        continue
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

    # If a recovered meet's entries also failed (upstream purged everything,
    # not just /meets), synthesize minimal racecard stubs from the
    # RacePrediction rows so the home page can still list those tracks.
    # Stubs lack runner detail; clicking through will show a graceful
    # "results pending" state via the existing race_detail flow.
    if db_recovered_predictions:
        try:
            from app.services.secretariat import TRACK_NAMES
        except Exception:
            TRACK_NAMES = {}
        seen_meet_ids_in_results = {
            r.get("race_id", "").rsplit("-", 1)[0]
            for r in all_races
            if r.get("race_id") and "-" in r.get("race_id", "")
        }
        for p in db_recovered_predictions:
            if not p.race_id:
                continue
            meet_id = p.race_id.rsplit("-", 1)[0] if "-" in p.race_id else ""
            if meet_id and meet_id in seen_meet_ids_in_results:
                continue  # entries fetch succeeded; don't overwrite
            if p.race_id in seen_race_ids:
                continue
            seen_race_ids.add(p.race_id)
            track_name = TRACK_NAMES.get((p.track_code or "").upper()) or (p.track_code or "Unknown")
            all_races.append({
                "race_id": p.race_id,
                "course": track_name,
                "course_id": p.track_code or "",
                "track_code": p.track_code or "",
                "race_name": p.race_name or "",
                "race_type": p.race_type or "",
                "surface": p.surface or "",
                "runners": [],  # no runner data when upstream is fully gone
                "off_dt": None,
                "post_time_et": p.post_time_et,
                "_stub_from_db": True,
            })

    # Sticky union — once a race is seen for this date, keep it on the list
    # for the rest of the day even if upstream prunes the meet from /meets
    # or /entries (which it does aggressively as cards finish, sometimes
    # even mid-card while the last race is still running). Without this,
    # tracks silently disappear from the home page during the racing day.
    sticky_key = f"na:racecards_full:sticky:{target_date.isoformat()}"
    sticky = await cache_get(sticky_key) or {"racecards": []}

    by_id: dict[str, dict] = {}
    for r in sticky.get("racecards", []) or []:
        rid = r.get("race_id")
        if rid:
            by_id[rid] = r
    # Live data wins on conflict (so scratches / ML changes propagate)
    for r in all_races:
        rid = r.get("race_id")
        if rid:
            by_id[rid] = r

    merged = list(by_id.values())
    payload = {"racecards": merged, "total": len(merged), "region": "usa"}
    await cache_set(sticky_key, payload, ex=86400)
    return payload


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
                    # Forwarded so post-race reflection (nightly_reflect.py) can
                    # reason about exotic structuring and value, not just W/L names.
                    "payoffs": race.get("payoffs") or [],
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
