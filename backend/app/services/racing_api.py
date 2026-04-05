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
    """Find a race by ID in the cached racecard list."""
    for day in (None, "tomorrow"):
        cache_key = f"racecards:all:{'today' if day is None else day}"
        cached = await cache_get(cache_key)
        if cached:
            for r in cached.get("racecards", []):
                if r.get("race_id") == race_id:
                    return _normalize_race(r)

    # Cache miss — fetch today's cards
    data = await get_racecards()
    for r in data.get("racecards", []):
        if r.get("race_id") == race_id:
            return r

    # Try tomorrow
    data = await get_racecards(date="tomorrow")
    for r in data.get("racecards", []):
        if r.get("race_id") == race_id:
            return r

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
