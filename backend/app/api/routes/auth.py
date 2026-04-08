"""
Auth routes: register, login, me, profile update, logout.

POST /api/auth/register   — create account, returns token + user
POST /api/auth/login      — authenticate, returns token + user
GET  /api/auth/me         — return current user (requires JWT)
PUT  /api/auth/profile    — update betting profile fields (requires JWT)
POST /api/auth/logout     — no-op (JWT is stateless; client drops the token)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import msgspec

from app.core.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.core.database import get_db
from app.models.user import User

router = APIRouter()


# ── Request body structs ───────────────────────────────────────────────────────

class RegisterRequest(msgspec.Struct):
    email: str
    password: str
    bankroll: float = 500.0
    risk_tolerance: str = "medium"
    experience_level: str = "beginner"
    region: str = "usa"


class LoginRequest(msgspec.Struct):
    email: str
    password: str


class ProfileUpdateRequest(msgspec.Struct):
    bankroll: float | None = None
    risk_tolerance: str | None = None
    experience_level: str | None = None
    region: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "bankroll": user.bankroll,
        "risk_tolerance": user.risk_tolerance,
        "experience_level": user.experience_level,
        "region": user.region,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=RegisterRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(req.password),
        bankroll=max(0.0, req.bankroll),
        risk_tolerance=req.risk_tolerance if req.risk_tolerance in ("low", "medium", "high") else "medium",
        experience_level=req.experience_level if req.experience_level in ("beginner", "intermediate", "advanced") else "beginner",
        region=req.region.strip() or "usa",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return JSONResponse({"token": token, "user": _user_dict(user)})


@router.post("/login")
async def login(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=LoginRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    email = req.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(user.id)
    return JSONResponse({"token": token, "user": _user_dict(user)})


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(_user_dict(user))


@router.put("/profile")
async def update_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=ProfileUpdateRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if req.bankroll is not None:
        user.bankroll = max(0.0, req.bankroll)
    if req.risk_tolerance in ("low", "medium", "high"):
        user.risk_tolerance = req.risk_tolerance
    if req.experience_level in ("beginner", "intermediate", "advanced"):
        user.experience_level = req.experience_level
    if req.region:
        user.region = req.region.strip()

    await db.commit()
    await db.refresh(user)
    return JSONResponse(_user_dict(user))


@router.post("/logout")
async def logout() -> JSONResponse:
    # JWT is stateless — client is responsible for dropping the token
    return JSONResponse({"message": "Logged out"})
