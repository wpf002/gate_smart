"""Deleting 63,741 keys from production Redis gets one safety property:
the data must demonstrably live somewhere else first.

Commit e9ad052 moved the Equibase history to Postgres in April 2026 and left
the Redis copies behind. These tests pin the precondition (refuse if Postgres
is empty), the default (count, do not delete), and the batching.
"""
import pytest
from fastapi import HTTPException

import app.api.routes.admin_redis as mod


class FakeRedis:
    def __init__(self, keys, used_memory=1_570_000_000):
        self.keys = list(keys)
        self.used = used_memory
        self.unlink_calls: list[int] = []

    async def info(self, _section):
        return {"used_memory": self.used}

    async def scan_iter(self, match=None, count=1000):
        import fnmatch as fn

        for k in list(self.keys):
            if match is None or fn.fnmatch(k, match):
                yield k

    async def unlink(self, *keys):
        self.unlink_calls.append(len(keys))
        for k in keys:
            self.keys.remove(k)
        # 24 KB per key, roughly what the report measured
        self.used -= 24_000 * len(keys)
        return len(keys)


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class FakeSession:
    def __init__(self, counts):
        self._counts = list(counts)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, _stmt):
        return FakeResult(self._counts.pop(0))


@pytest.fixture
def wired(monkeypatch):
    """Point the purge at fakes for Redis and Postgres."""

    def _wire(keys, pg_counts):
        redis = FakeRedis(keys)
        import app.core.cache as cache_mod
        import app.core.database as db_mod

        monkeypatch.setattr(cache_mod, "_redis", redis, raising=False)
        monkeypatch.setattr(db_mod, "_AsyncSessionLocal", lambda: FakeSession(pg_counts), raising=False)
        return redis

    return _wire


EQUIBASE = [f"equibase:horse:h{i}" for i in range(1200)]
KEEP = ["paper:bank:s1", "paper:bets:s1", "accuracy:total", "ai_analysis:r1:balanced"]


@pytest.mark.asyncio
async def test_dry_run_counts_and_deletes_nothing(wired):
    redis = wired(EQUIBASE + KEEP, [684154, 318702])
    out = await mod.purge_orphaned_equibase(dry_run=True)
    assert out["matched_keys"] == 1200
    assert out["deleted_keys"] == 0
    assert len(redis.keys) == 1204
    assert out["freed_mb"] == 0


@pytest.mark.asyncio
async def test_purge_deletes_only_the_orphans(wired):
    redis = wired(EQUIBASE + KEEP, [684154, 318702])
    out = await mod.purge_orphaned_equibase(dry_run=False)
    assert out["deleted_keys"] == 1200
    assert sorted(redis.keys) == sorted(KEEP), "paper, accuracy and analysis keys must survive"
    assert out["freed_mb"] > 0


@pytest.mark.asyncio
async def test_refuses_when_postgres_has_no_past_performances(wired):
    redis = wired(EQUIBASE, [0, 318702])
    with pytest.raises(HTTPException) as err:
        await mod.purge_orphaned_equibase(dry_run=False)
    assert err.value.status_code == 409
    assert len(redis.keys) == 1200, "nothing may be deleted when the other copy is missing"


@pytest.mark.asyncio
async def test_refuses_when_postgres_has_no_charts(wired):
    redis = wired(EQUIBASE, [684154, 0])
    with pytest.raises(HTTPException):
        await mod.purge_orphaned_equibase(dry_run=False)
    assert len(redis.keys) == 1200


@pytest.mark.asyncio
async def test_unlinks_in_batches_rather_than_one_huge_call(wired):
    redis = wired(EQUIBASE, [684154, 318702])
    await mod.purge_orphaned_equibase(dry_run=False, batch_size=500)
    assert redis.unlink_calls == [500, 500, 200]


@pytest.mark.asyncio
async def test_no_orphans_is_a_no_op(wired):
    redis = wired(KEEP, [684154, 318702])
    out = await mod.purge_orphaned_equibase(dry_run=False)
    assert out["matched_keys"] == 0 and out["deleted_keys"] == 0
    assert sorted(redis.keys) == sorted(KEEP)
