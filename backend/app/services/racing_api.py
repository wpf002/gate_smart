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


async def get_racecards(date: str = None, region: str = "gb") -> dict:
    params = {"region": region}
    if date:
        params["date"] = date
    return await _get(
        "/racecards/pro",
        params=params,
        cache_key=f"racecards:{region}:{date or 'today'}",
        ttl=600,
    )


async def get_race(race_id: str) -> dict:
    return await _get(
        f"/racecards/{race_id}",
        cache_key=f"race:{race_id}",
        ttl=600,
    )


async def get_horse(horse_id: str) -> dict:
    return await _get(
        f"/horses/{horse_id}",
        cache_key=f"horse:{horse_id}",
        ttl=3600,
    )


async def get_horse_results(horse_id: str, limit: int = 10) -> dict:
    return await _get(
        f"/horses/{horse_id}/results",
        params={"limit": limit},
        cache_key=f"horse_results:{horse_id}:{limit}",
        ttl=3600,
    )


async def get_results(date: str = None, region: str = "gb") -> dict:
    params = {"region": region}
    if date:
        params["date"] = date
    return await _get(
        "/results",
        params=params,
        cache_key=f"results:{region}:{date or 'today'}",
        ttl=3600,
    )


async def search_horses(name: str) -> dict:
    return await _get(
        "/horses/search",
        params={"name": name},
    )


async def get_jockey(jockey_id: str) -> dict:
    return await _get(
        f"/jockeys/{jockey_id}",
        cache_key=f"jockey:{jockey_id}",
        ttl=3600,
    )


async def get_trainer(trainer_id: str) -> dict:
    return await _get(
        f"/trainers/{trainer_id}",
        cache_key=f"trainer:{trainer_id}",
        ttl=3600,
    )
