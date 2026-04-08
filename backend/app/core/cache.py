"""
Redis key schema:
  racecards:all:{day}              TTL 600s   — full racecard response (all regions)
  results:{region}:{date}          TTL 1800s  — results by region/date
  horse_search:{name}              TTL 3600s  — horse name search results
  ai_analysis:{race_id}:{mode}     TTL 300s   — cached Secretariat analysis
  scorecard:{race_id}              TTL 600s   — cached field scorecards
  debrief:{race_id}                TTL 86400s — post-race AI debrief
  alerts:fair:{race_id}:{horse_id} TTL 14400s — fair price per runner
  predictions:{race_id}            TTL 604800s — Secretariat prediction record
  accuracy:total                   no TTL     — total settled predictions counter
  accuracy:correct                 no TTL     — correct predictions counter
  paper:bank:{sid}                            — paper trading bank balance
  paper:bets:{sid}                            — paper trading bet history
  tracksense:map:{horse_id}                   — horse ID mapping
  tracksense:sectionals:{epc}                 — rolling 50-entry sectionals
  affiliate:clicks:{aff_id}:{date} TTL 86400s — daily affiliate click counter
  na:meets:{date}                  TTL 600s   — NA meet list
  na:entries:{meet_id}             TTL 600s   — NA meet entries
  na:results:{meet_id}             TTL 3600s  — NA meet results
  equibase:horse:{name_key}        no TTL     — 2023 result chart speed figures per horse
  equibase:pp:{name_key}           no TTL     — 2023 past performance records per horse (cap 30)
"""
import json
from typing import Any, Optional

import redis.asyncio as aioredis

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global _redis
    from app.core.config import settings
    url = settings.REDIS_URL
    if settings.REDIS_PASSWORD:
        # Inject password into URL: redis://[:password@]host:port
        url = url.replace("redis://", f"redis://:{settings.REDIS_PASSWORD}@", 1)
    _redis = await aioredis.from_url(url, decode_responses=True)


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


async def cache_keys(pattern: str) -> list:
    if _redis is None:
        return []
    return await _redis.keys(pattern)


async def cache_delete(key: str) -> None:
    if _redis is None:
        return
    await _redis.delete(key)


async def cache_incr(key: str, ttl: Optional[int] = None) -> int:
    """Increment a Redis counter. Pass ttl to auto-expire; omit for persistent counters."""
    if _redis is None:
        return 0
    val = await _redis.incr(key)
    if val == 1 and ttl is not None:
        await _redis.expire(key, ttl)
    return val
