"""
Async SQLAlchemy database setup.

Use:
    from app.core.database import get_db, AsyncSession

    @router.get("/foo")
    async def foo(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(SomeModel).where(...))
        return result.scalars().all()
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_engine = None
_AsyncSessionLocal = None


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    global _engine, _AsyncSessionLocal
    from app.core.config import settings
    from app.models import accuracy, equibase, user  # noqa: F401 — ensure models are registered

    _engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    _AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all only creates missing tables; columns added later need an
        # explicit ALTER. Idempotent — safe to run on every boot.
        from sqlalchemy import text
        for stmt in _STARTUP_MIGRATIONS:
            await conn.execute(text(stmt))


# Add to this list when a model gains a new column. Each statement must be
# idempotent ("IF NOT EXISTS"). Removed columns / renames are NOT auto-handled.
_STARTUP_MIGRATIONS: list[str] = [
    "ALTER TABLE llm_call_log ADD COLUMN IF NOT EXISTS user_id INTEGER",
    "CREATE INDEX IF NOT EXISTS ix_llm_call_log_user_id ON llm_call_log (user_id)",
    # Market context on predictions — favorite-agreement / calibration analysis.
    "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS field_size INTEGER",
    "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS top_pick_odds DOUBLE PRECISION",
    "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS favorite_odds DOUBLE PRECISION",
    "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS favorite_num VARCHAR(10)",
    "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS top_pick_is_favorite BOOLEAN",
]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialised — call init_db() at startup")
    async with _AsyncSessionLocal() as session:
        yield session


async def db_status() -> str:
    """Return 'connected' or 'disconnected' — used by health endpoint."""
    if _engine is None:
        return "disconnected"
    try:
        async with _engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return "connected"
    except Exception:
        return "disconnected"
