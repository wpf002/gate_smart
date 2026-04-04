import json
from typing import Any, Optional

import redis.asyncio as aioredis

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global _redis
    from app.core.config import settings
    _redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def cache_get(key: str) -> Optional[Any]:
    if _redis is None:
        return None
    val = await _redis.get(key)
    if val is None:
        return None
    return json.loads(val)


async def cache_set(key: str, value: Any, ex: Optional[int] = None) -> None:
    if _redis is None:
        return
    data = json.dumps(value)
    if ex is not None:
        await _redis.set(key, data, ex=ex)
    else:
        await _redis.set(key, data)
