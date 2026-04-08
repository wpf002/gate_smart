import uuid
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user
from app.core.cache import cache_get, cache_set
from app.core.database import get_db
from app.models.user import PaperBet as PaperBetModel, User
from app.services import racing_api

router = APIRouter()

INITIAL_BANK = 500.0
_BANK_KEY = "paper:bank:{sid}"
_BETS_KEY = "paper:bets:{sid}"


class PlaceBetRequest(msgspec.Struct):
    race_id: str
    horse_id: str
    horse_name: str
    bet_type: str       # win | place | each_way
    odds: str
    stake: float
    race_name: str = ""
    course: str = ""
    jockey: str = ""
    trainer: str = ""


class TopupRequest(msgspec.Struct):
    amount: float


# ── Odds parser ───────────────────────────────────────────────────────────────

def _parse_decimal_odds(odds: str) -> Optional[float]:
    if not odds or odds in ("?", "SP"):
        return None
    if "/" in odds:
        parts = odds.split("/")
        try:
            return int(parts[0]) / int(parts[1]) + 1
        except (ValueError, ZeroDivisionError, IndexError):
            return None
    try:
        d = float(odds)
        return d if d > 0 else None
    except ValueError:
        return None


# ── Session helper (guest mode only) ─────────────────────────────────────────

def _get_session(request: Request) -> str:
    sid = request.headers.get("X-Session-ID", "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    return sid


def _get_session_optional(request: Request) -> Optional[str]:
    return request.headers.get("X-Session-ID", "").strip() or None


# ── Redis helpers (guest mode) ────────────────────────────────────────────────

async def _get_bank(sid: str) -> float:
    val = await cache_get(_BANK_KEY.format(sid=sid))
    return float(val) if val is not None else INITIAL_BANK


async def _set_bank(sid: str, amount: float) -> None:
    await cache_set(_BANK_KEY.format(sid=sid), amount)


async def _get_bets(sid: str) -> list:
    val = await cache_get(_BETS_KEY.format(sid=sid))
    return val if isinstance(val, list) else []


async def _set_bets(sid: str, bets: list) -> None:
    await cache_set(_BETS_KEY.format(sid=sid), bets)


# ── Postgres helpers (auth mode) ──────────────────────────────────────────────

def _bet_to_dict(b: PaperBetModel) -> dict:
    return {
        "bet_id": b.bet_id,
        "race_id": b.race_id,
        "horse_id": b.horse_id,
        "horse_name": b.horse_name,
        "bet_type": b.bet_type,
        "odds": b.odds,
        "stake": b.stake,
        "status": b.status,
        "returns": b.returns,
        "pnl": b.pnl,
        "placed_at": b.placed_at,
        "settled_at": b.settled_at,
        "race_name": b.race_name,
        "course": b.course,
        "jockey": b.jockey,
        "trainer": b.trainer,
    }


async def _pg_get_bets(db: AsyncSession, user_id: int) -> list[dict]:
    result = await db.execute(
        select(PaperBetModel)
        .where(PaperBetModel.user_id == user_id)
        .order_by(PaperBetModel.id.desc())
    )
    return [_bet_to_dict(b) for b in result.scalars().all()]


# ── Settle logic (Redis / guest mode) ────────────────────────────────────────
# Called from races.py auto-settle background task — signature unchanged.

async def settle_race_bets(sid: str, race_id: str) -> list:
    """
    Fetch today's results, find the race, and settle all pending bets (Redis/guest mode).
    Returns list of newly-settled bets (may be empty).
    """
    bets = await _get_bets(sid)
    pending = [b for b in bets if b["race_id"] == race_id and b["status"] == "pending"]
    if not pending:
        return []

    try:
        results_data = await racing_api.get_results()
        race_result = None
        for r in results_data.get("results", []):
            if r.get("race_id") == race_id:
                race_result = r
                break
    except Exception:
        return []

    if not race_result:
        return []

    runners_by_id: dict = {}
    runners_by_name: dict = {}
    for rn in race_result.get("runners", []):
        hid = rn.get("horse_id", "")
        hname = (rn.get("horse_name") or rn.get("horse", "")).lower()
        if hid:
            runners_by_id[hid] = rn
        if hname:
            runners_by_name[hname] = rn

    total_runners = len(race_result.get("runners", []))
    place_positions = 1 if total_runners <= 4 else 2 if total_runners <= 7 else 3

    bank = await _get_bank(sid)
    settled_bets = []

    for bet in bets:
        if bet["race_id"] != race_id or bet["status"] != "pending":
            continue
        runner = runners_by_id.get(bet["horse_id"]) or runners_by_name.get(bet["horse_name"].lower())
        settled = _settle_bet(bet, runner, place_positions)
        bank += settled["returns"]
        settled_bets.append(settled)

    await _set_bank(sid, round(bank, 2))
    await _set_bets(sid, bets)
    return settled_bets


async def _settle_race_bets_pg(db: AsyncSession, user: User, race_id: str) -> list[dict]:
    """Settle all pending bets for a race in Postgres (auth mode)."""
    result = await db.execute(
        select(PaperBetModel).where(
            PaperBetModel.user_id == user.id,
            PaperBetModel.race_id == race_id,
            PaperBetModel.status == "pending",
        )
    )
    pending_bets = result.scalars().all()
    if not pending_bets:
        return []

    try:
        results_data = await racing_api.get_results()
        race_result = None
        for r in results_data.get("results", []):
            if r.get("race_id") == race_id:
                race_result = r
                break
    except Exception:
        return []

    if not race_result:
        return []

    runners_by_id: dict = {}
    runners_by_name: dict = {}
    for rn in race_result.get("runners", []):
        hid = rn.get("horse_id", "")
        hname = (rn.get("horse_name") or rn.get("horse", "")).lower()
        if hid:
            runners_by_id[hid] = rn
        if hname:
            runners_by_name[hname] = rn

    total_runners = len(race_result.get("runners", []))
    place_positions = 1 if total_runners <= 4 else 2 if total_runners <= 7 else 3

    settled_dicts = []
    for bet_row in pending_bets:
        runner = runners_by_id.get(bet_row.horse_id) or runners_by_name.get(bet_row.horse_name.lower())
        result_dict = _settle_bet(_bet_to_dict(bet_row), runner, place_positions)

        bet_row.status = result_dict["status"]
        bet_row.returns = result_dict["returns"]
        bet_row.pnl = result_dict["pnl"]
        bet_row.settled_at = result_dict["settled_at"]
        user.bankroll = round(user.bankroll + result_dict["returns"], 2)
        settled_dicts.append(result_dict)

    await db.commit()
    return settled_dicts


def _settle_bet(bet: dict, runner: Optional[dict], place_positions: int) -> dict:
    """Pure settle logic shared by Redis and Postgres modes."""
    if not runner:
        bet["status"] = "void"
        bet["returns"] = bet["stake"]
        bet["pnl"] = 0.0
        bet["settled_at"] = datetime.now(timezone.utc).isoformat()
        return bet

    try:
        position = int(str(runner.get("position", 999)))
    except (TypeError, ValueError):
        position = 999

    decimal_odds = _parse_decimal_odds(bet["odds"])
    stake = bet["stake"]
    bet_type = bet["bet_type"]
    placed = position <= place_positions

    if bet_type == "win":
        won = position == 1
        returns = stake * decimal_odds if (won and decimal_odds) else 0.0
    elif bet_type == "place":
        won = placed
        place_odds = ((decimal_odds - 1) / 4 + 1) if decimal_odds else None
        returns = stake * place_odds if (won and place_odds) else 0.0
    elif bet_type == "each_way":
        win_stake = stake / 2
        place_stake = stake / 2
        win_ret = win_stake * decimal_odds if (position == 1 and decimal_odds) else 0.0
        place_odds = ((decimal_odds - 1) / 4 + 1) if decimal_odds else None
        place_ret = place_stake * place_odds if (placed and place_odds) else 0.0
        returns = win_ret + place_ret
        won = position == 1 or placed
    else:
        won = position == 1
        returns = stake * decimal_odds if (won and decimal_odds) else 0.0

    bet["status"] = "won" if won else "lost"
    bet["returns"] = round(returns, 2)
    bet["pnl"] = round(returns - stake, 2)
    bet["settled_at"] = datetime.now(timezone.utc).isoformat()
    return bet


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/bet")
async def place_bet(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=PlaceBetRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    if req.stake <= 0:
        raise HTTPException(status_code=400, detail="stake must be positive")

    if user:
        # ── Postgres / auth mode ──────────────────────────────────────────────
        bank = user.bankroll
        if req.stake > bank:
            raise HTTPException(status_code=400, detail=f"insufficient funds (bank: £{bank:.2f})")

        # Prevent duplicate pending bets for same horse in same race
        dup = await db.execute(
            select(PaperBetModel).where(
                PaperBetModel.user_id == user.id,
                PaperBetModel.race_id == req.race_id,
                PaperBetModel.horse_id == req.horse_id,
                PaperBetModel.bet_type == req.bet_type,
                PaperBetModel.status == "pending",
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="A pending bet for this horse already exists")

        bet_row = PaperBetModel(
            user_id=user.id,
            bet_id=str(uuid.uuid4())[:8],
            race_id=req.race_id,
            horse_id=req.horse_id,
            horse_name=req.horse_name,
            bet_type=req.bet_type,
            odds=req.odds,
            stake=req.stake,
            placed_at=datetime.now(timezone.utc).isoformat(),
            race_name=req.race_name,
            course=req.course,
            jockey=req.jockey,
            trainer=req.trainer,
        )
        user.bankroll = round(bank - req.stake, 2)
        db.add(bet_row)
        await db.commit()
        await db.refresh(bet_row)
        return JSONResponse({"bet": _bet_to_dict(bet_row), "bank": user.bankroll})

    else:
        # ── Redis / guest mode ────────────────────────────────────────────────
        sid = _get_session(request)
        bank = await _get_bank(sid)
        if req.stake > bank:
            raise HTTPException(status_code=400, detail=f"insufficient funds (bank: £{bank:.2f})")

        # Prevent duplicates in Redis mode
        existing = await _get_bets(sid)
        for b in existing:
            if (b.get("race_id") == req.race_id and b.get("horse_id") == req.horse_id
                    and b.get("bet_type") == req.bet_type and b.get("status") == "pending"):
                raise HTTPException(status_code=409, detail="A pending bet for this horse already exists")

        bet = {
            "bet_id": str(uuid.uuid4())[:8],
            "race_id": req.race_id,
            "horse_id": req.horse_id,
            "horse_name": req.horse_name,
            "bet_type": req.bet_type,
            "odds": req.odds,
            "stake": req.stake,
            "status": "pending",
            "returns": 0.0,
            "pnl": 0.0,
            "placed_at": datetime.now(timezone.utc).isoformat(),
            "settled_at": "",
            "race_name": req.race_name,
            "course": req.course,
            "jockey": req.jockey,
            "trainer": req.trainer,
        }
        new_bank = round(bank - req.stake, 2)
        await _set_bank(sid, new_bank)
        bets = await _get_bets(sid)
        bets.append(bet)
        await _set_bets(sid, bets)
        return JSONResponse({"bet": bet, "bank": new_bank})


@router.post("/settle/{race_id}")
async def settle(
    race_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    if user:
        settled = await _settle_race_bets_pg(db, user, race_id)
    else:
        sid = _get_session(request)
        settled = await settle_race_bets(sid, race_id)

    if not settled:
        return JSONResponse({"message": "no pending bets found for this race", "settled": []})
    return JSONResponse({"message": f"{len(settled)} bet(s) settled", "settled": settled})


@router.get("/bets")
async def list_bets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    if user:
        bets = await _pg_get_bets(db, user.id)
    else:
        sid = _get_session(request)
        bets = list(reversed(await _get_bets(sid)))
    return JSONResponse({"bets": bets, "total": len(bets)})


@router.get("/bank")
async def get_bank_balance(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    if user:
        return JSONResponse({"bank": user.bankroll})
    sid = _get_session(request)
    return JSONResponse({"bank": await _get_bank(sid)})


@router.get("/stats")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    if user:
        bets = await _pg_get_bets(db, user.id)
        bank = user.bankroll
    else:
        sid = _get_session(request)
        bets = await _get_bets(sid)
        bank = await _get_bank(sid)

    settled = [b for b in bets if b["status"] in ("won", "lost")]
    pending = [b for b in bets if b["status"] == "pending"]
    won_list = [b for b in settled if b["status"] == "won"]

    total_wagered = sum(b["stake"] for b in settled)
    total_returns = sum(b["returns"] for b in settled)
    net_pnl = round(total_returns - total_wagered, 2)
    roi = round((net_pnl / total_wagered * 100) if total_wagered > 0 else 0.0, 1)

    return JSONResponse({
        "bank": bank,
        "total_bets": len(bets),
        "pending_bets": len(pending),
        "settled_bets": len(settled),
        "won_bets": len(won_list),
        "lost_bets": len(settled) - len(won_list),
        "total_wagered": round(total_wagered, 2),
        "total_returns": round(total_returns, 2),
        "net_pnl": net_pnl,
        "roi": roi,
    })


@router.post("/reset")
async def reset(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    if user:
        # Delete all bets and reset bankroll to 500
        result = await db.execute(
            select(PaperBetModel).where(PaperBetModel.user_id == user.id)
        )
        for bet_row in result.scalars().all():
            await db.delete(bet_row)
        user.bankroll = INITIAL_BANK
        await db.commit()
    else:
        sid = _get_session(request)
        await _set_bank(sid, INITIAL_BANK)
        await _set_bets(sid, [])
    return JSONResponse({"bank": INITIAL_BANK, "message": "Simulator reset to £500"})


@router.post("/bank/topup")
async def topup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=TopupRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    if req.amount <= 0 or req.amount > 10000:
        raise HTTPException(status_code=400, detail="amount must be 1–10000")

    if user:
        user.bankroll = round(user.bankroll + req.amount, 2)
        await db.commit()
        return JSONResponse({"bank": user.bankroll})
    else:
        sid = _get_session(request)
        bank = await _get_bank(sid)
        new_bank = round(bank + req.amount, 2)
        await _set_bank(sid, new_bank)
        return JSONResponse({"bank": new_bank})
