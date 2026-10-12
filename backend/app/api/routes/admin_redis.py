"""
Admin: what is actually in Redis, and what it costs.

Redis is the most expensive service on the Railway bill after furlong's worker
— 1.53 GB resident, about $14/month — and nobody could say what was in it. The
key schema in app/core/cache.py says which prefixes exist but not which ones
are large, and the service has no public endpoint, so the question could only
be answered from inside the app.

It matters because the obvious cost fix is wrong here. Setting `maxmemory` with
`allkeys-lru` would evict whatever is coldest, and the keys with no TTL include
`paper:bank:*` and `paper:bets:*` (a user's paper-trading balance and bet
history), `accuracy:total` / `accuracy:correct` (the counters behind the
accuracy page), and `equibase:*` (scraped speed figures). Evicting those is
data loss, not caching.

So: measure first. This samples each prefix rather than walking every key, so
it stays cheap on a live instance. Read-only, owner-gated.
"""
import fnmatch

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db  # noqa: F401 — kept for router symmetry
from app.models.user import User

router = APIRouter()

# The prefixes app/core/cache.py documents, plus a catch-all. Order matters:
# the first pattern a key matches wins, so put specific ones first.
PREFIXES: list[str] = [
    "racecards:*",
    "results:*",
    "horse_search:*",
    "ai_analysis:*",
    "scorecard:*",
    "debrief:*",
    "alerts:fair:*",
    "predictions:*",
    "accuracy:*",
    "paper:*",
    "tracksense:*",
    "affiliate:*",
    "na:*",
    "equibase:horse:*",
    "equibase:pp:*",
    "equibase:*",
]

# Keys sampled per prefix for the average-size estimate. 50 is enough to size a
# prefix within a few percent and costs a few milliseconds.
SAMPLE_PER_PREFIX = 50


def _admin_emails() -> set[str]:
    raw = (settings.DAILY_REPORT_EMAIL or "").lower()
    return {e.strip() for e in raw.split(",") if e.strip()}


def _require_admin(user: User) -> None:
    if (user.email or "").lower() not in _admin_emails():
        raise HTTPException(status_code=403, detail="Admin only")


def _bucket_for(key: str) -> str:
    for pattern in PREFIXES:
        if fnmatch.fnmatch(key, pattern):
            return pattern
    return "other"


async def redis_usage_summary() -> dict:
    """Key count, sampled average size, estimated bytes and TTL coverage per
    prefix — plus what Redis itself reports for total memory.

    `persistent_share` is the fraction of sampled keys with no expiry. A prefix
    that is entirely persistent cannot be freed by an eviction policy without
    losing data, which is the whole question this exists to answer.

    Separate from the route so the nightly scheduler job can log the same
    numbers: the route needs an owner login, and the log does not.
    """
    from app.core import cache as cache_mod

    redis = getattr(cache_mod, "_redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis is not connected")

    info = await redis.info("memory")
    buckets: dict[str, dict] = {}

    # SCAN rather than KEYS: KEYS blocks the server for the length of the
    # keyspace, and this runs against production.
    async for key in redis.scan_iter(count=1000):
        bucket = buckets.setdefault(
            _bucket_for(key),
            {"keys": 0, "sampled": 0, "sampled_bytes": 0, "persistent": 0, "example": key},
        )
        bucket["keys"] += 1
        if bucket["sampled"] < SAMPLE_PER_PREFIX:
            try:
                size = await redis.memory_usage(key) or 0
            except Exception:
                size = 0
            ttl = await redis.ttl(key)
            bucket["sampled"] += 1
            bucket["sampled_bytes"] += size
            if ttl == -1:  # -1 = no expiry, -2 = key is gone
                bucket["persistent"] += 1

    rows = []
    for prefix, b in buckets.items():
        avg = b["sampled_bytes"] / b["sampled"] if b["sampled"] else 0
        estimated = avg * b["keys"]
        rows.append(
            {
                "prefix": prefix,
                "keys": b["keys"],
                "avg_bytes": round(avg),
                "estimated_mb": round(estimated / (1024 * 1024), 1),
                "estimated_monthly_usd": round(estimated / (1024**3) * 10, 2),
                "persistent_share": round(b["persistent"] / b["sampled"], 2) if b["sampled"] else None,
                "example_key": b["example"],
            }
        )
    rows.sort(key=lambda r: r["estimated_mb"], reverse=True)

    return {
        "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 1),
        "used_memory_rss_mb": round(info.get("used_memory_rss", 0) / (1024 * 1024), 1),
        "maxmemory_mb": round(info.get("maxmemory", 0) / (1024 * 1024), 1),
        "maxmemory_policy": info.get("maxmemory_policy"),
        "total_keys": sum(r["keys"] for r in rows),
        "by_prefix": rows,
    }


@router.get("/usage")
async def redis_usage(user: User = Depends(get_current_user)):
    """Owner-gated view of the same summary the nightly job logs."""
    _require_admin(user)
    return await redis_usage_summary()
