"""
Admin: what is actually in Redis, and what it costs.

Redis is the most expensive service on the Railway bill after furlong's worker
— 1.53 GB resident, about $14/month — and nobody could say what was in it. The
key schema in app/core/cache.py says which prefixes exist but not which ones
are large, and the service has no public endpoint, so the question could only
be answered from inside the app.

It matters because the obvious cost fix is wrong here. Setting `maxmemory` with
`allkeys-lru` would evict whatever is coldest, and some keys carry no TTL:
`paper:bank:*` and `paper:bets:*` (a user's paper-trading balance and bet
history) and `accuracy:total` / `accuracy:correct` (the counters behind the
accuracy page). Evicting those is data loss, not caching.

Measuring first is what found the actual problem. `equibase:*` is 63,741 keys
and ~1.5 GB of the 1.5 GB in use — and it is orphaned. Commit e9ad052 moved
that data to Postgres in April 2026 ("Redis is a cache — not the right home
for 600k+ static historical records"); the tables hold 684k past-performance
rows and 319k chart rows, the read path queries them, and nothing has written
or read the Redis copies since. They have been billed for six months.

So: measure, then purge what is provably dead. Both are owner-gated.
"""
import fnmatch
import os

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

# Stop walking after this many keys. A full SCAN of a 1.5 GB keyspace takes
# minutes of round-trips, and the first run of this report did exactly that:
# the job fired and said nothing for long enough to look broken. Past the cap
# the counts are scaled by DBSIZE, which is close enough to decide a policy and
# bounded enough to run on a schedule.
SCAN_CAP = int(os.environ.get("REDIS_REPORT_SCAN_CAP", "50000"))


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
    total_keys = await redis.dbsize()
    buckets: dict[str, dict] = {}
    scanned = 0

    # SCAN rather than KEYS: KEYS blocks the server for the length of the
    # keyspace, and this runs against production.
    async for key in redis.scan_iter(count=1000):
        scanned += 1
        if scanned > SCAN_CAP:
            break
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

    # Past the cap, each scanned key stands for several in the keyspace.
    scale = (total_keys / scanned) if scanned and total_keys > scanned else 1.0

    rows = []
    for prefix, b in buckets.items():
        avg = b["sampled_bytes"] / b["sampled"] if b["sampled"] else 0
        keys_estimated = round(b["keys"] * scale)
        estimated = avg * keys_estimated
        rows.append(
            {
                "prefix": prefix,
                "keys": keys_estimated,
                "avg_bytes": round(avg),
                "estimated_mb": round(estimated / (1024 * 1024), 1),
                "estimated_monthly_usd": round(estimated / (1024**3) * 10, 2),
                "persistent_share": round(b["persistent"] / b["sampled"], 2) if b["sampled"] else None,
                "example_key": b["example"],
            }
        )
    rows.sort(key=lambda r: r["estimated_mb"], reverse=True)

    return {
        "scanned_keys": scanned,
        "scan_truncated": scale > 1.0,
        "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 1),
        "used_memory_rss_mb": round(info.get("used_memory_rss", 0) / (1024 * 1024), 1),
        "maxmemory_mb": round(info.get("maxmemory", 0) / (1024 * 1024), 1),
        "maxmemory_policy": info.get("maxmemory_policy"),
        "total_keys": total_keys,
        "by_prefix": rows,
    }


@router.get("/usage")
async def redis_usage(user: User = Depends(get_current_user)):
    """Owner-gated view of the same summary the nightly job logs."""
    _require_admin(user)
    return await redis_usage_summary()

# ── purging the orphaned Equibase copy ───────────────────────────────────────

ORPHAN_PATTERN = "equibase:*"


async def purge_orphaned_equibase(dry_run: bool = True, batch_size: int = 500) -> dict:
    """Delete the Redis copy of data that lives in Postgres.

    The precondition is the whole safety story: both Postgres tables must hold
    rows for more horses than this would delete keys for. If the migration were
    ever rolled back, or the tables emptied, this refuses rather than deleting
    the last copy.

    UNLINK rather than DEL: it frees the memory on a background thread, so
    63,741 keys do not block the server that is also serving the race card.
    """
    from sqlalchemy import func, select

    from app.core import cache as cache_mod
    from app.core.database import _AsyncSessionLocal
    from app.models.equibase import HorsePastPerformance, HorseResultChart

    redis = getattr(cache_mod, "_redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis is not connected")

    async with _AsyncSessionLocal() as session:
        pp_rows = (await session.execute(select(func.count(HorsePastPerformance.id)))).scalar() or 0
        chart_rows = (await session.execute(select(func.count(HorseResultChart.id)))).scalar() or 0
    precondition = {"past_performance_rows": int(pp_rows), "result_chart_rows": int(chart_rows)}
    if pp_rows <= 0 or chart_rows <= 0:
        raise HTTPException(
            status_code=409,
            detail=f"Refusing to purge: Postgres does not hold this data ({precondition})",
        )

    before = (await redis.info("memory")).get("used_memory", 0)
    matched = 0
    deleted = 0
    pending: list[str] = []

    async for key in redis.scan_iter(match=ORPHAN_PATTERN, count=1000):
        matched += 1
        if dry_run:
            continue
        pending.append(key)
        if len(pending) >= batch_size:
            deleted += await redis.unlink(*pending)
            pending.clear()
    if pending and not dry_run:
        deleted += await redis.unlink(*pending)

    after = (await redis.info("memory")).get("used_memory", 0)
    return {
        "dry_run": dry_run,
        "pattern": ORPHAN_PATTERN,
        "precondition": precondition,
        "matched_keys": matched,
        "deleted_keys": deleted,
        "used_memory_mb_before": round(before / (1024 * 1024), 1),
        "used_memory_mb_after": round(after / (1024 * 1024), 1),
        "freed_mb": round((before - after) / (1024 * 1024), 1),
    }


@router.post("/purge-orphans")
async def purge_orphans(dry_run: bool = True, user: User = Depends(get_current_user)):
    """Count (dry_run=true, the default) or delete the orphaned Equibase keys."""
    _require_admin(user)
    return await purge_orphaned_equibase(dry_run=dry_run)
