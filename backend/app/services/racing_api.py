"""
The Racing API client — Pro plan, plus the North America data add-on.
Endpoint docs: https://api.theracingapi.com
Rate limit: 5 req/sec. Redis caching keeps us well within this.
"""
import contextvars
import re

import httpx
from fastapi import HTTPException

from app.core.cache import cache_get, cache_set
from app.core.config import settings

BASE_URL = "https://api.theracingapi.com/v1"

# The contest scores every bet off a 2-unit stake. UK tote dividends are
# declared to 1 unit, so they are doubled to match.
STAKE_UNITS = 2

# Upstream allows 5 req/sec. A bare semaphore still lets short bursts exceed
# that when responses are fast — which returned 429s and failed 183 dates of a
# backfill. This paces requests to a fixed minimum interval instead.
#
# It applies ONLY to bulk jobs. Applied globally it also throttled live user
# requests: a "tomorrow" racecard fans out to ~48 upstream calls (track-recovery
# probes plus entries), which at 4/sec meant 12 seconds of pure waiting and
# produced read timeouts in production. Live traffic never caused the 429s —
# a multi-thousand-request backfill did.
_MIN_REQUEST_INTERVAL = 1 / 4.0
_rate_lock = None
_last_request_at = 0.0

_bulk_mode: "contextvars.ContextVar[bool]" = contextvars.ContextVar("racing_api_bulk", default=False)


def set_bulk_mode(enabled: bool = True) -> None:
    """Throttle upstream calls. Backfills and other bulk jobs should enable this;
    request handlers must not, or user-facing latency collapses."""
    _bulk_mode.set(enabled)


async def _rate_limit() -> None:
    import asyncio
    import time as _time
    global _rate_lock, _last_request_at
    if not _bulk_mode.get():
        return
    if _rate_lock is None:
        _rate_lock = asyncio.Lock()
    async with _rate_lock:
        wait = _MIN_REQUEST_INTERVAL - (_time.monotonic() - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_at = _time.monotonic()


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

    await _rate_limit()
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


# Racing Post headgear codes. The NA feed writes equipment out in words; the
# core feed writes a letter, so it is expanded here rather than in four places
# downstream.
_HEADGEAR = {
    "b": "blinkers", "v": "visor", "h": "hood", "p": "cheekpieces",
    "t": "tongue tie", "e": "eye shield", "z": "hood",
}

# Flags the core feed puts against a runner's past record.
_RESULT_FLAGS = {
    "C": "course winner", "D": "distance winner",
    "CD": "course and distance winner", "BF": "beaten favourite",
}


def _headgear_text(code: str, first_run: str) -> str:
    """"b" plus a headgear_run of 1 is first-time blinkers, which is an angle."""
    code = (code or "").strip().lower()
    if not code:
        return ""
    worn = ", ".join(_HEADGEAR.get(c, c) for c in code if c.strip())
    if not worn:
        return ""
    return f"first-time {worn}" if str(first_run or "") == "1" else worn


def _flags_text(flags) -> str:
    if not flags:
        return ""
    return ", ".join(_RESULT_FLAGS.get(f, f) for f in flags if f)


def _trainer_14_text(rec, rtf) -> str:
    """The barn's last fortnight, as one readable phrase."""
    if not isinstance(rec, dict):
        return ""
    runs, wins, pct = rec.get("runs"), rec.get("wins"), rec.get("percent")
    if not runs:
        return ""
    out = f"{wins or 0} from {runs} in the last 14 days ({pct or 0}%)"
    if rtf:
        out += f", {rtf}% of the string running to form"
    return out


def _normalize_runner(r: dict) -> dict:
    """Map a core-feed runner onto the names the app already uses.

    The US and international feeds describe the same things with different
    words. Reconciling them here means the race page, the prompt and the
    contest never have to ask which feed a race came from:

      draw                 -> post_position   the gate, whatever it's called
      headgear + _run      -> equipment       "first-time blinkers", not "b"
      wind_surgery         -> medication      the nearest thing to a Lasix note
      ofr                  -> official_rating the class figure, as in the US
                                              the claim price is the class signal
      last_run             -> days_since_run
      past_results_flags   -> course_distance_record

    The core feed only publishes declared runners, so a horse that won't run is
    absent rather than flagged — scratched is therefore always False, which is
    what the rest of the app expects to find.
    """
    headgear = _headgear_text(r.get("headgear"), r.get("headgear_run"))
    wind = (r.get("wind_surgery") or "").strip()
    return {
        **r,
        "horse_name": r.get("horse") or r.get("horse_name", ""),
        "cloth_number": r.get("number") or r.get("cloth_number"),
        "stall_number": r.get("draw") or r.get("stall_number"),
        "post_position": r.get("draw") or r.get("post_position"),
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
        "equipment": headgear or r.get("equipment", ""),
        "headgear_first_time": headgear.startswith("first-time"),
        "medication": wind and f"wind surgery {wind}" or r.get("medication", ""),
        "days_since_run": r.get("last_run") or r.get("days_since_run"),
        "course_distance_record": _flags_text(r.get("past_results_flags")),
        "trainer_form": _trainer_14_text(r.get("trainer_14_days"), r.get("trainer_rtf")),
        "trainer_14_days": r.get("trainer_14_days"),
        "scratched": False,
        "non_runner": False,
    }


def _normalize_race(r: dict) -> dict:
    """Map a core-feed race onto the names the app already uses.

    Same reconciliation as the runner: `type` is the US feed's `race_type`,
    `race_status` is its `is_cancelled`, and a jumps race says so explicitly so
    nothing downstream applies flat-racing pace logic to a three-mile chase.
    """
    distance = r.get("distance") or (
        f"{r['distance_f']}f" if r.get("distance_f") else None
    )
    status = (r.get("race_status") or "").lower()
    runners = [_normalize_runner(runner) for runner in r.get("runners", [])]
    jumps = (r.get("jumps") or "").strip()
    race_type = r.get("race_type") or r.get("type") or ""
    try:
        field_size = int(r.get("field_size") or 0) or len(runners)
    except (TypeError, ValueError):
        field_size = len(runners)
    return {
        **r,
        "time": r.get("off_time") or r.get("time", ""),
        "title": r.get("race_name") or r.get("title", ""),
        "distance": distance,
        "going_detail": r.get("going_detailed") or r.get("going"),
        "race_type": race_type,
        # Chase, hurdle and National Hunt flat are a different sport from the
        # flat: stamina and jumping decide them, not gate speed.
        "jumps": jumps,
        "is_jumps": bool(jumps) or race_type.lower() in ("chase", "hurdle", "nh flat"),
        "is_cancelled": status == "abandoned" or bool(r.get("is_abandoned")),
        "has_results": status in ("result", "resulted", "finished"),
        "field_size": field_size,
        # The track's own published changes, under the name the US view uses.
        "changes": [c for c in ([r.get("rail_movements")] if r.get("rail_movements") else []) if c],
        # The UK equivalent of a morning line: the forecast price for the card.
        "betting_forecast": r.get("betting_forecast") or "",
        "runners": runners,
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
    """One race from whichever feed owns its id.

    The two feeds write ids differently and there is no overlap, so the shape
    of the id picks the feed:

      IND_1775520000000-1   North America add-on, {MEET_ID}-{race_number}
      rac_32299222618       core feed, which is where every non-US race lives

    Without the second branch every international card was a dead link: the
    detail page asked for a rac_ id, this looked for a meet, and 404'd.
    """
    if race_id.startswith("rac_"):
        raw = await _get(
            f"/racecards/{race_id}/pro",
            cache_key=f"race:pro:{race_id}",
            ttl=300,
        )
        return _normalize_race(raw)

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


async def get_results(date: str = None, region: str = None, **filters) -> dict:
    """Results for a day, or an advanced query across the last twelve months.

    With no filters this is /results/today or /results/YYYY-MM-DD, unchanged.
    Pass any of start_date, end_date, course, type, going, race_class,
    min_distance_y, max_distance_y, age_band or sex_restriction and it moves to
    /results, which is the endpoint that actually answers "every class 2 handicap
    on soft ground over a mile since January".
    """
    advanced = _result_filters(region=region, **filters)
    if any(k != "region" for k in advanced):
        path = "/results"
        params = advanced
        if date and date not in ("today",) and "start_date" not in params:
            params["start_date"] = params["end_date"] = date
        params.setdefault("limit", 100)
    else:
        path = f"/results/{date}" if date and date != "today" else "/results/today"
        params = {"region": region} if region else {}

    raw = await _get(
        path,
        params=params or None,
        cache_key=f"results:{path}:{_params_key(params)}",
        ttl=1800,
    )
    results = [_normalize_result(r) for r in raw.get("results", [])]
    return {"results": results, "total": len(results)}


# ── Horses ────────────────────────────────────────────────────────────────────

# ── Advanced result queries ──────────────────────────────────────────────────
#
# /results and every per-entity results endpoint take the same filter set, so
# it's built once. Array parameters go as repeated keys, which httpx does for a
# list value, and the API's own names are used verbatim rather than aliased —
# a caller reading their docs can pass what the docs say.

_RESULT_FILTERS = (
    "start_date", "end_date", "region", "course", "type", "going", "race_class",
    "min_distance_y", "max_distance_y", "age_band", "sex_restriction",
)


def _result_filters(**kwargs) -> dict:
    """The subset of advanced filters the caller actually set."""
    out = {}
    for key in _RESULT_FILTERS:
        val = kwargs.get(key)
        if val in (None, "", [], ()):
            continue
        out[key] = list(val) if isinstance(val, (list, tuple, set)) else val
    return out


def _params_key(params: dict) -> str:
    """A stable cache-key fragment for a parameter dict."""
    parts = []
    for k in sorted(params or {}):
        v = params[k]
        parts.append(f"{k}={','.join(map(str, v)) if isinstance(v, list) else v}")
    return "|".join(parts) or "none"


# ── Courses and regions ──────────────────────────────────────────────────────

async def get_course_regions() -> list[dict]:
    """Every country the feed knows, as {region, region_code}. 55 of them."""
    data = await _get(
        "/courses/regions",
        cache_key="courses:regions:v1",
        ttl=30 * 24 * 3600,  # countries do not come and go
    )
    return data if isinstance(data, list) else (data or {}).get("regions", [])


async def get_courses(region_codes: list[str] | None = None) -> dict:
    """Tracks, optionally narrowed to some countries.

    The parameter is region_codes, plural and repeated — a single region_code
    is silently ignored and you get the whole world back.
    """
    params = {"region_codes": list(region_codes)} if region_codes else None
    return await _get(
        "/courses",
        params=params,
        cache_key=f"courses:{_params_key(params or {})}",
        ttl=7 * 24 * 3600,
    )


# ── Pro racecards ────────────────────────────────────────────────────────────
#
# /racecards/standard and /racecards/pro carry the same races; pro carries far
# more about each runner. Per runner it adds every bookmaker's price (29 on a
# sample Catterick card) with its own movement history, RPR, topspeed, official
# rating, the Racing Post spotlight comment and stable tour quotes, the
# trainer's last-14-days record and RTF, headgear and wind-surgery flags, plus
# date of birth, colour, sex, owner and breeder. Odds are UK and IRE only.

RACECARDS_PRO_PAGE = 500  # the endpoint's own maximum


async def get_racecards_pro(date: str = None, region_codes: list[str] | None = None,
                            course_ids: list[str] | None = None) -> dict:
    """Every Pro racecard for a day, following the pagination to the end."""
    base: dict = {}
    if date:
        base["date"] = date
    if region_codes:
        base["region_codes"] = list(region_codes)
    if course_ids:
        base["course_ids"] = list(course_ids)

    cache_key = f"racecards:pro:{_params_key(base)}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    cards: list[dict] = []
    skip = 0
    while True:
        page = await _get("/racecards/pro", params={**base, "limit": RACECARDS_PRO_PAGE, "skip": skip})
        rows = page.get("racecards") or []
        cards.extend(rows)
        # skip caps at 500, so one more page is all the endpoint will give.
        if len(rows) < RACECARDS_PRO_PAGE or skip >= RACECARDS_PRO_PAGE:
            break
        skip += RACECARDS_PRO_PAGE

    out = {"racecards": cards, "total": len(cards)}
    await cache_set(cache_key, out, ex=600)
    return out


async def get_big_races() -> dict:
    """The feed's own list of upcoming Group and Grade races worldwide."""
    return await _get("/racecards/big-races", cache_key="racecards:big_races:v1", ttl=3600)


async def get_odds_history(race_id: str, horse_id: str) -> dict:
    """Every bookmaker's price for one runner, with its movement since market open."""
    return await _get(
        f"/odds/{race_id}/{horse_id}",
        cache_key=f"odds_history:{race_id}:{horse_id}",
        ttl=120,  # prices move; this is the shortest useful life
    )


def normalize_core_result(res: dict) -> dict:
    """A core-feed result in the shape the contest already grades.

    The two feeds price a race completely differently. A US chart carries a
    payoff per runner per pool; a British one carries tote dividends at the race
    level, declared to a 1-unit stake and inclusive of it. Both are converted to
    the contest's 2-unit basis here so nothing downstream has to know which is
    which.

    Only the pools the contest actually settles are mapped: win, place, exacta
    and trifecta. There is no show pool in British or Irish racing — the place
    pool pays two to four places depending on the field — so a show bet grades
    on the same top-three rule the contest uses everywhere and is left unpriced
    rather than invented.
    """
    def _num(v):
        try:
            f = float(str(v).replace(",", "").replace("£", "").replace("€", "").strip())
            return round(f * STAKE_UNITS, 2) if f > 0 else None
        except (TypeError, ValueError, AttributeError):
            return None

    runners = sorted(
        (r for r in (res.get("runners") or []) if str(r.get("position") or "").isdigit()),
        key=lambda r: int(r["position"]),
    )
    win = _num(res.get("tote_win"))
    places = [x for x in str(res.get("tote_pl") or "").split(",") if x.strip()]
    out = []
    for i, r in enumerate(runners):
        row = {
            **r,
            "horse_name": r.get("horse") or r.get("horse_name") or "",
            "position": r.get("position"),
            "win_payoff": win if i == 0 else None,
            "place_payoff": _num(places[i]) if i < len(places) else None,
            "show_payoff": None,
        }
        out.append(row)

    payoffs = []
    for code, key in (("E", "tote_ex"), ("T", "tote_trifecta")):
        amount = _num(res.get(key))
        if amount:
            payoffs.append({"wager_type": code, "payoff_amount": amount,
                            "base_amount": STAKE_UNITS})
    return {**res, "runners": out, "payoffs": payoffs}


async def get_core_result(race_id: str) -> dict | None:
    """One finished core-feed race, graded-ready. None while it is still to run."""
    try:
        raw = await _get(f"/results/{race_id}", cache_key=f"core_result:{race_id}", ttl=3600)
    except Exception:
        return None
    if not (raw or {}).get("runners"):
        return None
    return normalize_core_result(raw)


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
    """Breeding, date of birth, sex and colour for one horse.

    Refused outright until the Pro upgrade, which is why anything asking for a
    horse profile quietly got nothing back.
    """
    if not horse_id:
        raise HTTPException(status_code=400, detail="horse_id required")
    return await _get(
        f"/horses/{horse_id}/pro",
        cache_key=f"horse_pro:{horse_id}",
        ttl=7 * 24 * 3600,  # a date of birth does not change
    )


async def get_horse_results(horse_id: str, limit: int = 10, **filters) -> dict:
    """A horse's own past runs, newest first.

    Takes the same advanced filters as /results — start_date, end_date, region,
    course, type, going, race_class, min_distance_y, max_distance_y, age_band,
    sex_restriction — so "this horse on soft ground over a mile" is one call.
    """
    if not horse_id:
        raise HTTPException(status_code=400, detail="horse_id required")
    params = {"limit": max(1, min(int(limit or 10), 100))}
    params.update(_result_filters(**filters))
    return await _get(
        f"/horses/{horse_id}/results",
        params=params,
        cache_key=f"horse_results:{horse_id}:{_params_key(params)}",
        ttl=6 * 3600,
    )


async def get_horse_distance_times(horse_id: str) -> dict:
    """Per-distance times and win rates for one horse."""
    return await _get(
        f"/horses/{horse_id}/analysis/distance-times",
        cache_key=f"horse_dist_times:{horse_id}",
        ttl=24 * 3600,
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

    import asyncio as _asyncio
    _probe_sem = _asyncio.Semaphore(6)

    async def _probe(prefix: str):
        candidate = f"{prefix}_{utc_midnight_ms}"
        neg_key = f"na:probe:neg:{candidate}"
        if await cache_get(neg_key):
            return prefix, None  # recently confirmed dark — don't hammer upstream
        async with _probe_sem:
            try:
                return prefix, await get_na_meet_entries(candidate)
            except Exception:
                await cache_set(neg_key, 1, ex=1800)
                return prefix, None

    # Probed concurrently — sequentially this was ~39 round-trips on a cold
    # "tomorrow" card and dominated the response.
    probed = await _asyncio.gather(*(_probe(p) for p in missing))

    for prefix, entries in probed:
        candidate = f"{prefix}_{utc_midnight_ms}"
        neg_key = f"na:probe:neg:{candidate}"
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

    await _rate_limit()
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

    # The meet's UTC-midnight epoch is encoded in the meet_id suffix
    # (``MTH_1783728000000``). Used both to anchor offset-form times and to
    # sanity-check epoch-form ones.
    base = None
    try:
        cand = int(str(meet_id).split("_", 1)[1])
        if cand >= 86_400_000:
            base = cand
    except (IndexError, ValueError):
        base = None

    if ptl >= 86_400_000:
        resolved = ptl  # already a full epoch-ms timestamp
    elif base is not None:
        resolved = base + ptl  # within-day offset anchored to meet midnight
    else:
        return None  # offset form but no meet-midnight base to anchor to

    # Sanity clamp: a legitimate post time falls within the meet day (allowing
    # for evening cards that cross into the next UTC day). If the resolved value
    # lands wildly off the meet date — a new or malformed upstream encoding we
    # haven't seen — refuse it and return None so the caller emits no off_dt at
    # all, rather than a bogus datetime that could mislabel the race as
    # "finished". This is the general backstop that keeps ANY future post_time
    # weirdness from resurrecting the 1970 finished-race bug.
    if base is not None:
        _DAY = 86_400_000
        if not (base - _DAY <= resolved <= base + 2 * _DAY):
            return None
    return resolved


def _weather_summary(weather) -> str:
    """Flatten the meet weather object into one line.

    Rain matters to a handicapper because it changes the going (and can move a
    turf race to dirt), so precipitation chance is kept alongside the description.
    """
    if isinstance(weather, str):
        return weather
    if not isinstance(weather, dict):
        return ""
    desc = weather.get("current_weather_description") or weather.get("forecast_weather_description") or ""
    precip = weather.get("forecast_precipitation")
    parts = [p for p in [desc] if p]
    if precip not in (None, ""):
        try:
            parts.append(f"{int(precip)}% precip")
        except (TypeError, ValueError):
            pass
    return ", ".join(parts)


def _fraction_seconds(frac: dict | None) -> float | None:
    """A fraction/winning-time object -> seconds as a float.

    The feed gives each split as {minutes, seconds, hundredths}; hundredths is
    the sub-second remainder (":24.52" arrives as seconds=24, hundredths=52).
    """
    if not isinstance(frac, dict):
        return None
    try:
        minutes = int(frac.get("minutes") or 0)
        seconds = int(frac.get("seconds") or 0)
        hundredths = int(frac.get("hundredths") or 0)
    except (TypeError, ValueError):
        return None
    total = minutes * 60 + seconds + hundredths / 100.0
    return round(total, 2) if total > 0 else None


def _extract_fractions(fraction: dict | None) -> list[float]:
    """Ordered split times (seconds) for a race — the pace shape."""
    if not isinstance(fraction, dict):
        return []
    out = []
    for i in range(1, 6):
        secs = _fraction_seconds(fraction.get(f"fraction_{i}"))
        if secs:
            out.append(secs)
    return out


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
        # Live tote money. horse_data_pools carries the WIN pool amount and the
        # current fractional odds — the price the public is actually betting,
        # which is far more informative than the static morning line.
        live_odds, win_pool = None, None
        for pool in entry.get("horse_data_pools") or []:
            if (pool.get("pool_type_name") or "").upper() == "WIN":
                live_odds = pool.get("fractional_odds") or None
                try:
                    win_pool = float(pool.get("amount"))
                except (TypeError, ValueError):
                    win_pool = None
                break
        live_odds = entry.get("live_odds") or live_odds
        ml = entry.get("morning_line_odds", "")

        runners.append({
            "horse_id": str(entry.get("registration_number", "")),
            "horse_name": entry.get("horse_name", ""),
            "horse": entry.get("horse_name", ""),
            "jockey": jockey_name,
            "jockey_id": (jockey.get("id") if isinstance(jockey, dict) else None),
            "trainer": trainer_name,
            "trainer_id": (trainer.get("id") if isinstance(trainer, dict) else None),
            "program_number": str(entry.get("program_number", "")),
            "number": str(entry.get("program_number", "")),
            "cloth_number": str(entry.get("program_number", "")),
            # Post position is the actual gate — distinct from the saddle-cloth
            # number once entries are coupled or horses scratch. Drives pace/trip.
            "post_position": entry.get("post_pos"),
            "age": "",
            "sex": "",
            "weight": entry.get("weight", ""),
            "form": "",
            # Live price when the tote is up, morning line as the fallback.
            "odds": live_odds or ml,
            "morning_line_odds": ml,
            "live_odds": live_odds,
            "win_pool": win_pool,
            "sp": ml,
            # Classic handicapping angles the feed had all along: equipment
            # changes (blinkers on/off) and medication (Lasix).
            "equipment": entry.get("equipment") or "",
            "medication": entry.get("medication") or "",
            # Pedigree — the only form signal available for first-time starters.
            "sire": entry.get("sire_name") or "",
            "dam": entry.get("dam_name") or "",
            "damsire": entry.get("dam_sire_name") or "",
            "coupled_type": entry.get("coupled_type") or "",
            "official_rating": None,
            "non_runner": is_scratched,
            "scratched": is_scratched,
            "status": "scratched" if is_scratched else "",
            "claiming_price": entry.get("claiming") or entry.get("claiming_price"),
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
        # Thoroughbred vs Quarter Horse vs Arabian. Without this the model
        # applies thoroughbred pace logic to 350-yard QH sprints, where it
        # simply doesn't apply.
        "breed": race.get("breed") or "",
        # Eligibility conditions are real class context — a state-bred
        # fillies-and-mares race is a materially softer spot than open company.
        "age_restriction": race.get("age_restriction_description") or "",
        "sex_restriction": race.get("sex_restriction_description") or "",
        "race_restriction": race.get("race_restriction_description") or "",
        "claim_price_min": race.get("min_claim_price") or race.get("minimum_claim_price"),
        "claim_price_max": race.get("max_claim_price") or race.get("maximum_claim_price"),
        # D / T / etc. — dirt vs turf vs inner track, finer than the description.
        "course_type": race.get("course_type") or race.get("surface") or "",
        "weather": _weather_summary(meet.get("weather")),
        # Scratches / rider changes posted by the track.
        "changes": [
            c.get("text") for c in (race.get("changes") or [])
            if c.get("text") and c.get("text") != "No Changes"
        ],
        # Which pools are actually offered — authoritative, so P&L never
        # charges for a wager the track didn't run.
        "wager_pools": [
            p.get("pool_name") for p in (race.get("race_pools") or []) if p.get("pool_name")
        ],
        "minutes_to_post": race.get("mtp"),
        "is_cancelled": bool(race.get("is_cancelled")),
        "has_results": bool(race.get("has_results")),
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

    # Fetch each meet's chart concurrently. Sequentially this ran at roughly
    # 0.4 req/sec against a 5 req/sec allowance — the bound was our own waiting,
    # not the API. The semaphore keeps us comfortably inside the limit.
    import asyncio as _asyncio
    _sem = _asyncio.Semaphore(4)

    async def _fetch(meet_id: str):
        async with _sem:
            try:
                return meet_id, await get_na_meet_results(meet_id)
            except Exception:
                return meet_id, None

    meet_ids = [m.get("meet_id", "") for m in meets if m.get("meet_id")]
    fetched = dict(await _asyncio.gather(*(_fetch(mid) for mid in meet_ids)))

    all_results = []
    for meet in meets:
        meet_id = meet.get("meet_id", "")
        if not meet_id:
            continue
        try:
            results_data = fetched.get(meet_id)
            if not results_data:
                continue
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
                        "jockey": f"{r.get('jockey_first_name','')} {r.get('jockey_last_name','')}".strip(),
                        "trainer": f"{r.get('trainer_first_name','')} {r.get('trainer_last_name','')}".strip(),
                        "owner": (r.get("owner_last_name") or "").strip(),
                        "sire": r.get("sire_name") or "",
                        "weight_carried": r.get("weight_carried"),
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
                    # Race shape: split times plus the winning time. This is the
                    # only genuine pace data in the feed — how fast the race was
                    # actually run — and the raw material for building our own
                    # speed/pace baselines over time.
                    "fractions": _extract_fractions(race.get("fraction")),
                    "winning_time": _fraction_seconds((race.get("fraction") or {}).get("winning_time")),
                    "distance": race.get("distance_description", ""),
                    "distance_f": _parse_na_distance_furlongs(
                        race.get("distance_description", ""),
                        race.get("distance_value"),
                        race.get("distance_unit", ""),
                    ),
                    "going": race.get("track_condition_description") or "",
                    "breed": race.get("breed") or "",
                    "purse": race.get("total_purse"),
                    "race_class": race.get("race_class", ""),
                    "off_time": race.get("off_time"),
                    # Beyond the charted top 3 — the rest of the field, so we can
                    # record that a horse ran and finished off the board.
                    "also_ran": race.get("also_ran") or [],
                    "scratches": race.get("scratches") or [],
                    # Which wagers the track actually offered.
                    "wager_types": [
                        w.get("wager_description") for w in (race.get("wager_types") or [])
                        if w.get("wager_description")
                    ],
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


async def search_owners(name: str) -> dict:
    """Owners. The fourth searchable party, and the one we never asked for."""
    return await _get(
        "/owners/search",
        params={"name": name},
        cache_key=f"owner_search:{name.lower()}",
        ttl=3600,
    )


# Every group that has both /search and /{id}/results, mapped from the singular
# name a caller would use to the plural the API wants in the path.
ENTITY_GROUPS = {
    "horse": "horses", "jockey": "jockeys", "trainer": "trainers",
    "owner": "owners", "sire": "sires", "dam": "dams", "damsire": "damsires",
}


async def search_entity(name: str, entity_type: str) -> dict:
    """Name search for any of the seven searchable parties."""
    group = ENTITY_GROUPS.get((entity_type or "").lower())
    if not group:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {sorted(ENTITY_GROUPS)}")
    return await _get(
        f"/{group}/search",
        params={"name": name},
        cache_key=f"{group}_search:{(name or '').lower()}",
        ttl=3600,
    )


async def get_entity_results(entity_id: str, entity_type: str, limit: int = 20,
                             **filters) -> dict:
    """Historical results for any horse, jockey, trainer, owner, sire, dam or
    damsire, with the full advanced filter set applied."""
    group = ENTITY_GROUPS.get((entity_type or "").lower())
    if not group:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {sorted(ENTITY_GROUPS)}")
    params = {"limit": max(1, min(int(limit or 20), 100))}
    if filters.get("skip"):
        params["skip"] = int(filters.pop("skip"))
    filters.pop("skip", None)
    params.update(_result_filters(**filters))
    return await _get(
        f"/{group}/{entity_id}/results",
        params=params,
        cache_key=f"{group}_results:{entity_id}:{_params_key(params)}",
        ttl=6 * 3600,
    )


# ── Person form, from the Pro analysis endpoints ─────────────────────────────
#
# These carry USA races even though the core racecards and results do not, so a
# US trainer or jockey has real numbers here: runners, the finish spread, win %,
# actual-vs-expected, and £1 level-stake profit. They are the only place we can
# get a true start count, which is what the form archive has never had.
#
# The window is the plan's rolling 12 months. A sample of 172 Flavien Prat rides
# came back entirely 2025-2026, so treat every figure as recent form and label
# it that way — it is not a career record.

PERSON_FORM_TTL = 24 * 3600  # people's numbers move slowly; the card does not


async def find_person_id(name: str, person_type: str) -> str | None:
    """The API's own id for a trainer, jockey or owner, matched on exact name first."""
    if not name or person_type not in ("trainer", "jockey", "owner"):
        return None
    try:
        data = await search_entity(name, person_type)
    except Exception:
        return None
    rows = (data or {}).get("search_results") or []
    target = name.strip().lower()

    def _tokens(v: str) -> set[str]:
        # The API writes "Chad C Brown" where a card says "Chad Brown", and
        # suffixes drift ("Jr" vs "Jr."). Compare on the words, so a middle
        # initial on either side doesn't lose the match.
        return {t for t in re.split(r"[^a-z]+", (v or "").lower()) if len(t) > 1}

    exact = next((r for r in rows if (r.get("name") or "").strip().lower() == target), None)
    if exact:
        return exact.get("id")
    want = _tokens(name)
    if not want:
        return None
    # Every word of the query has to appear, so "Chad Brown" reaches
    # "Chad C Brown" but never "Chad Summers".
    loose = next((r for r in rows if want <= _tokens(r.get("name"))), None)
    return (loose or {}).get("id") if loose else None


async def get_person_analysis(person_id: str, person_type: str, facet: str = "courses") -> dict:
    """Raw analysis payload: per-facet runners, finishes, win %, a/e and P/L.

    Facets differ by group: trainers have courses, distances, jockeys, owners
    and horse-age; jockeys have courses, distances, trainers and owners; owners
    have courses, distances, jockeys and trainers.
    """
    group = ENTITY_GROUPS.get(person_type, "jockeys")
    return await _get(
        f"/{group}/{person_id}/analysis/{facet}",
        cache_key=f"person_analysis:{group}:{person_id}:{facet}",
        ttl=PERSON_FORM_TTL,
    )


def summarise_person_analysis(payload: dict) -> dict | None:
    """Roll a courses breakdown up into one headline record.

    a/e is weighted by runners — averaging the per-course figures would let a
    single ride at an outlying track count as much as two hundred.
    """
    if not payload:
        return None
    rows = payload.get("courses") or []
    total = payload.get("total_runners") or payload.get("total_rides") or 0
    if not rows or not total:
        return None
    starts = sum(int(r.get("runners") or r.get("rides") or 0) for r in rows)
    wins = sum(int(r.get("1st") or 0) for r in rows)
    placed = sum(int(r.get("1st") or 0) + int(r.get("2nd") or 0) + int(r.get("3rd") or 0) for r in rows)
    profit = sum(float(r.get("1_pl") or 0) for r in rows)
    ae_num = sum(float(r.get("a/e") or 0) * int(r.get("runners") or r.get("rides") or 0) for r in rows)
    if not starts:
        return None
    return {
        "starts": starts,
        "wins": wins,
        "win_rate": round(wins / starts, 4),
        "itm_rate": round(placed / starts, 4),
        "ae": round(ae_num / starts, 2) if starts else None,
        "profit_per_unit": round(profit / starts, 3),
        "total_profit": round(profit, 2),
    }


RESULTS_PAGE = 100          # the endpoint's own maximum
SEASON_MAX_PAGES = 12       # 1,200 races is more than any one yard runs here


def _twelve_month_chunks(start, end):
    """Split a range into windows the endpoint will accept.

    /results and the per-entity results endpoints reject any span wider than
    twelve months with a 422 — but they accept a twelve-month window anywhere in
    history, which is what makes a year-by-year record possible at all. A wider
    range asked for in one call just fails, so it is cut up here.
    """
    import datetime as _dt
    out = []
    lo = start
    while lo <= end:
        hi = min(end, lo.replace(year=lo.year + 1) - _dt.timedelta(days=1))
        out.append((lo, hi))
        lo = hi + _dt.timedelta(days=1)
    return out


async def get_entity_window(entity_id: str, entity_type: str, start, end,
                            name: str = "", label: str = "") -> dict | None:
    """A trainer's or jockey's record for one calendar year, with a real
    denominator.

    The profile page could only ever quote 2023, because our own form archive
    keeps top-three finishes and never wrote down a loss. This endpoint returns
    whole races — every runner, whatever it finished — so counting the person's
    own runs across a date range gives starts as well as wins.

    It covers USA: Chad Brown comes back with 41 races in 2026, Saratoga and
    Belmont among them, finishing positions included. The same limit as the rest
    of the analysis data applies though — this is the group-races-and-selected-
    handicaps dataset, so it is a record in stakes company, not a full season.
    The caller has to say so.
    """
    if not entity_id or entity_type not in ("trainer", "jockey"):
        return None
    import datetime as _dt

    today = _dt.date.today()
    end = min(end, today)
    if start > today or start > end:
        return None

    cache_key = f"window:{entity_type}:{entity_id}:{start}:{end}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    want = {t for t in re.split(r"[^a-z]+", (name or "").lower()) if len(t) > 1}
    starts = wins = placed = 0
    seen_races = 0
    for lo, hi in _twelve_month_chunks(start, end):
        for page in range(SEASON_MAX_PAGES):
            try:
                res = await get_entity_results(
                    entity_id, entity_type, limit=RESULTS_PAGE,
                    start_date=lo.isoformat(), end_date=hi.isoformat(),
                    skip=page * RESULTS_PAGE,
                )
            except Exception:
                break
            races = res.get("results") or []
            if not races:
                break
            seen_races += len(races)
            for race in races:
                for run in race.get("runners") or []:
                    # The endpoint returns the whole race, so the person's own
                    # runners have to be picked out of the field.
                    who = (run.get(entity_type) or "").lower()
                    if want and not want <= {t for t in re.split(r"[^a-z]+", who) if len(t) > 1}:
                        continue
                    starts += 1
                    pos = str(run.get("position") or "")
                    if pos == "1":
                        wins += 1
                    if pos in ("1", "2", "3"):
                        placed += 1
            if len(races) < RESULTS_PAGE:
                break

    if not starts:
        return None
    out = {
        "label": label,
        "from": start.isoformat(),
        "races": seen_races,
        "starts": starts,
        "wins": wins,
        "placed": placed,
        "win_rate": round(wins / starts, 4),
        "itm_rate": round(placed / starts, 4),
        "through": end.isoformat(),
    }
    await cache_set(cache_key, out, ex=6 * 3600)
    return out


async def get_entity_season(entity_id: str, entity_type: str, year: int,
                            name: str = "") -> dict | None:
    """One calendar year. A thin wrapper so callers don't build dates."""
    import datetime as _dt
    return await get_entity_window(
        entity_id, entity_type, _dt.date(year, 1, 1), _dt.date(year, 12, 31),
        name=name, label=str(year))


async def find_pedigree_id(name: str, kind: str) -> str | None:
    """Id for a sire, dam or damsire. `kind` is sires | dams | damsires."""
    if not name or kind not in ("sires", "dams", "damsires"):
        return None
    # Feed names carry a country suffix — "Tapit (USA)" — and cards often don't.
    bare = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name).strip()
    try:
        data = await _get(
            f"/{kind}/search",
            params={"name": bare},
            cache_key=f"{kind}_search:{bare.lower()}",
            ttl=7 * 24 * 3600,  # pedigree names never change
        )
    except Exception:
        return None
    rows = (data or {}).get("search_results") or []
    want = bare.lower()
    exact = next((r for r in rows
                  if re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", r.get("name") or "").strip().lower() == want),
                 None)
    return (exact or (rows[0] if rows else {})).get("id")


async def get_pedigree_analysis(ped_id: str, kind: str, facet: str) -> dict:
    """Progeny analysis for a sire/dam/damsire. facet is distances | classes."""
    return await _get(
        f"/{kind}/{ped_id}/analysis/{facet}",
        cache_key=f"pedigree:{kind}:{ped_id}:{facet}",
        ttl=7 * 24 * 3600,
    )


async def get_person_facet(person_id: str, person_type: str, facet: str) -> dict | None:
    """One analysis facet, or None. facet e.g. distances, jockeys, horse-age."""
    try:
        return await get_person_analysis(person_id, person_type, facet)
    except Exception:
        return None


async def get_person_form(name: str, person_type: str) -> dict | None:
    """Recent-form record for one trainer, jockey or owner, or None if unmatched."""
    person_id = await find_person_id(name, person_type)
    if not person_id:
        return None
    try:
        payload = await get_person_analysis(person_id, person_type, "courses")
    except Exception:
        return None
    summary = summarise_person_analysis(payload)
    if not summary:
        return None
    summary["id"] = person_id
    summary["courses"] = payload.get("courses") or []
    summary["name"] = (payload.get("trainer") or payload.get("jockey")
                       or payload.get("owner") or name)
    return summary
