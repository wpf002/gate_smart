from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv()

from app.api.routes import races, horses, betting, ai_advisor, education, tracksense, simulator, alerts, affiliate, auth
from app.core.cache import init_redis
from app.core.config import settings
from app.core.database import init_db
from app.core.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    try:
        await init_db()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Database init failed (non-fatal): {e}")
    yield


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

    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "redis": "connected" if redis_ok else "disconnected",
        "database": db_ok,
        "version": "1.0.0",
    }
