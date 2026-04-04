"""
The Racing API client — all horse racing data flows through here.
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


def _normalize_runner(r: dict) -> dict:
    """Map free-tier runner fields to the names the frontend expects."""
    return {
        **r,
        "horse_name": r.get("horse") or r.get("horse_name", ""),
        "cloth_number": r.get("number") or r.get("cloth_number"),
        "stall_number": r.get("draw") or r.get("stall_number"),
        "official_rating": r.get("ofr") or r.get("official_rating"),
        "weight": r.get("lbs"),
        # odds not provided in free tier
        "odds": r.get("odds") or r.get("sp") or "SP",
    }


def _normalize_race(r: dict) -> dict:
    """Map free-tier race fields to the names the frontend expects."""
    distance_f = r.get("distance_f")
    distance = f"{distance_f}f" if distance_f else r.get("distance")
    return {
        **r,
        "time": r.get("off_time") or r.get("time", ""),
        "title": r.get("race_name") or r.get("title", ""),
        "distance": distance,
        "runners": [_normalize_runner(runner) for runner in r.get("runners", [])],
    }


async def get_racecards(date: str = None, region: str = None) -> dict:
    params = {}
    if date:
        params["day"] = date
    else:
        params["day"] = "today"
    if region:
        params["region"] = region

    raw = await _get(
        "/racecards/free",
        params=params,
        cache_key=f"racecards:{region or 'all'}:{date or 'today'}",
        ttl=600,
    )
    races = [_normalize_race(r) for r in raw.get("racecards", [])]
    return {"racecards": races, "total": len(races)}


async def get_race(race_id: str) -> dict:
    """
    Free tier has no single-race endpoint — find it in the cached list instead.
    Falls back to fetching today's list if not cached yet.
    """
    # Try today's cache first
    for cache_key in [
        "racecards:all:today",
        "racecards:gb:today",
        "racecards::today",
    ]:
        cached = await cache_get(cache_key)
        if cached:
            races = cached.get("racecards", [])
            for r in races:
                if r.get("race_id") == race_id:
                    return _normalize_race(r)

    # Cache miss — fetch today's cards and search
    data = await get_racecards()
    for r in data.get("racecards", []):
        if r.get("race_id") == race_id:
            return r

    raise HTTPException(status_code=404, detail="Race not found")


async def get_horse(horse_id: str) -> dict:
    """Horse detail — not available on free tier. Return stub from runner data."""
    raise HTTPException(
        status_code=402,
        detail="Horse detail requires a paid Racing API plan",
    )


async def get_horse_results(horse_id: str, limit: int = 10) -> dict:
    raise HTTPException(
        status_code=402,
        detail="Horse results require a paid Racing API plan",
    )


async def get_results(date: str = None, region: str = None) -> dict:
    raise HTTPException(
        status_code=402,
        detail="Results require a paid Racing API plan",
    )


async def search_horses(name: str) -> dict:
    """Horse search — not available on free tier."""
    raise HTTPException(
        status_code=402,
        detail="Horse search requires a paid Racing API plan",
    )


async def get_jockey(jockey_id: str) -> dict:
    raise HTTPException(
        status_code=402,
        detail="Jockey detail requires a paid Racing API plan",
    )


async def get_trainer(trainer_id: str) -> dict:
    raise HTTPException(
        status_code=402,
        detail="Trainer detail requires a paid Racing API plan",
    )
