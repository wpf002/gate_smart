from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from app.api.routes import races, horses, betting, ai_advisor, education, tracksense, simulator, alerts, affiliate
from app.core.config import settings
from app.core.cache import init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield


app = FastAPI(
    title="GateSmart API",
    description="AI-powered horse racing betting intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GateSmart API"}
