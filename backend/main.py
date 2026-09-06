from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv()

from app.api.routes import races, horses, betting, ai_advisor, education, tracksense, simulator, alerts, affiliate, auth, accuracy, admin_cost, watchlist, people
from app.core.cache import init_redis
from app.core.config import settings
from app.core.database import init_db
from app.core.limiter import limiter
from app.core.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    try:
        await init_db()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Database init failed (non-fatal): {e}")

    # Lightweight column migrations — Base.metadata.create_all only creates
    # new tables, not new columns on existing tables. Keep these idempotent.
    try:
        from app.core import database as _db
        from sqlalchemy import text as _text
        async with _db._engine.begin() as _conn:
            await _conn.execute(_text(
                "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS lock_source VARCHAR(30)"
            ))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Column migration failed (non-fatal): {e}")

    scheduler = create_scheduler()
    if scheduler is not None:
        scheduler.start()
        print("[scheduler] Nightly jobs scheduled and running", flush=True)
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="GateSmart API",
    description="AI-powered horse racing betting intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(races.router, prefix="/api/races", tags=["Races"])
app.include_router(horses.router, prefix="/api/horses", tags=["Horses"])
app.include_router(betting.router, prefix="/api/betting", tags=["Betting"])
app.include_router(ai_advisor.router, prefix="/api/advisor", tags=["AI Advisor"])
app.include_router(education.router, prefix="/api/education", tags=["Education"])
app.include_router(tracksense.router, prefix="/api/tracksense", tags=["TrackSense"])
app.include_router(simulator.router, prefix="/api/simulator", tags=["Simulator"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(affiliate.router, prefix="/api/affiliate", tags=["Affiliate"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(accuracy.router, prefix="/api/accuracy", tags=["Accuracy"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(people.router, prefix="/api/people", tags=["People"])
app.include_router(admin_cost.router, prefix="/api/admin/cost", tags=["Admin"])


@app.get("/health")
async def health():
    redis_ok = False
    try:
        from app.core.cache import _redis
        if _redis:
            await _redis.ping()
            redis_ok = True
    except Exception:
        pass

    from app.core.database import db_status
    db_ok = await db_status()

    # Age of the last smoke-check run, in seconds. The scheduler owns every
    # nightly job and the smoke check itself, so if it dies the process keeps
    # serving HTTP and nothing complains. An external watcher reads this to tell
    # "up" apart from "up but doing nothing".
    smoke_age = None
    try:
        import datetime as _dt

        from app.core.cache import cache_get
        stamp = await cache_get("smoke:last_run_at")
        if stamp:
            last = _dt.datetime.fromisoformat(stamp)
            # The smoke check stamps datetime.utcnow(), which is NAIVE. Comparing
            # that to an aware now() raises, and the except below would have
            # swallowed it — leaving the field permanently null and the
            # dead-man's switch permanently red for the wrong reason.
            if last.tzinfo is None:
                last = last.replace(tzinfo=_dt.timezone.utc)
            smoke_age = int((_dt.datetime.now(_dt.timezone.utc) - last).total_seconds())
    except Exception:
        pass

    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "redis": "connected" if redis_ok else "disconnected",
        "database": db_ok,
        "scheduler_age_seconds": smoke_age,
        "version": "1.0.0",
    }
