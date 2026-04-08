import uuid
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user
from app.core.cache import cache_get, cache_set
from app.core.database import get_db
from app.models.user import PaperBet as PaperBetModel, User
from app.services import racing_api

router = APIRouter()

INITIAL_BANK = 500.0
# Bank is still tracked in Redis for speed (just a float, acceptable to lose on restart)
_BANK_KEY = "paper:bank:{key}"


class PlaceBetRequest(msgspec.Struct):
    race_id: str
    horse_id: str
    horse_name: str
    bet_type: str
    odds: str
    stake: float
    race_name: str = ""
    course: str = ""
    jockey: str = ""
    trainer: str = ""
    owner: str = ""


class TopupRequest(msgspec.Struct):
    amount: float


# ── Identity helpers ──────────────────────────────────────────────────────────
# Returns (user_id, session_id) — exactly one will be set.

def _identity(request: Request, user: Optional[User]):
    if user:
        return user.id, None
    sid = request.headers.get("X-Session-ID", "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    return None, sid


def _bank_key(user_id: Optional[int], session_id: Optional[str]) -> str:
    key = f"u:{user_id}" if user_id else f"s:{session_id}"
    return _BANK_KEY.format(key=key)


# ── Bank helpers (Redis — fast, acceptable to lose) ───────────────────────────

async def _get_bank(user_id: Optional[int], session_id: Optional[str]) -> float:
    if user_id:
        # Auth users: bank is on the User row — caller passes it in
        return INITIAL_BANK  # fallback; callers use user.bankroll directly
    val = await cache_get(_bank_key(None, session_id))
    return float(val) if val is not None else INITIAL_BANK


async def _set_bank(user_id: Optional[int], session_id: Optional[str], amount: float) -> None:
    if session_id:
        await cache_set(_bank_key(None, session_id), amount)


# ── Postgres helpers ──────────────────────────────────────────────────────────

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
        "owner": b.owner,
    }


async def _pg_get_bets(db: AsyncSession, user_id: Optional[int], session_id: Optional[str]) -> list[dict]:
    if user_id:
        q = select(PaperBetModel).where(PaperBetModel.user_id == user_id)
    else:
        q = select(PaperBetModel).where(PaperBetModel.session_id == session_id)
    result = await db.execute(q.order_by(PaperBetModel.id.desc()))
    return [_bet_to_dict(b) for b in result.scalars().all()]


# ── Settle helpers ────────────────────────────────────────────────────────────

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


def _settle_bet(bet: dict, runner: Optional[dict], place_positions: int) -> dict:
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


async def _settle_race_pg(
    db: AsyncSession,
    user_id: Optional[int],
    session_id: Optional[str],
    race_id: str,
    user: Optional[User] = None,
) -> tuple[list[dict], str]:
    """Returns (settled_bets, status) where status is 'settled'|'no_bets'|'no_results'|'error'."""
    if user_id:
        q = select(PaperBetModel).where(
            PaperBetModel.user_id == user_id,
            PaperBetModel.race_id == race_id,
            PaperBetModel.status == "pending",
        )
    else:
        q = select(PaperBetModel).where(
            PaperBetModel.session_id == session_id,
            PaperBetModel.race_id == race_id,
            PaperBetModel.status == "pending",
        )
    result = await db.execute(q)
    pending_bets = result.scalars().all()
    if not pending_bets:
        return [], "no_bets"

    try:
        results_data = await racing_api.get_results()
        race_result = next(
            (r for r in results_data.get("results", []) if r.get("race_id") == race_id),
            None,
        )
    except Exception:
        return [], "error"

    if not race_result:
        return [], "no_results"

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
        if user:
            user.bankroll = round(user.bankroll + result_dict["returns"], 2)
        else:
            bank = await _get_bank(None, session_id)
            await _set_bank(None, session_id, round(bank + result_dict["returns"], 2))
        settled_dicts.append(result_dict)

    await db.commit()
    return settled_dicts, "settled"


# Keep this for backward compat (called from races.py auto-settle)
async def settle_race_bets(sid: str, race_id: str) -> list:
    return []  # no-op; Redis path removed


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

    user_id, session_id = _identity(request, user)

    # Bank check
    if user:
        bank = user.bankroll
    else:
        bank = await _get_bank(None, session_id)

    if req.stake > bank:
        raise HTTPException(status_code=400, detail=f"insufficient funds (bank: £{bank:.2f})")

    # Dedup: no two pending bets for same horse+race+type
    if user_id:
        dup_q = select(PaperBetModel).where(
            PaperBetModel.user_id == user_id,
            PaperBetModel.race_id == req.race_id,
            PaperBetModel.horse_id == req.horse_id,
            PaperBetModel.bet_type == req.bet_type,
            PaperBetModel.status == "pending",
        )
    else:
        dup_q = select(PaperBetModel).where(
            PaperBetModel.session_id == session_id,
            PaperBetModel.race_id == req.race_id,
            PaperBetModel.horse_id == req.horse_id,
            PaperBetModel.bet_type == req.bet_type,
            PaperBetModel.status == "pending",
        )
    if (await db.execute(dup_q)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A pending bet for this horse already exists")

    bet_row = PaperBetModel(
        user_id=user_id,
        session_id=session_id,
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
        owner=req.owner,
    )

    new_bank = round(bank - req.stake, 2)
    if user:
        user.bankroll = new_bank
    else:
        await _set_bank(None, session_id, new_bank)

    db.add(bet_row)
    await db.commit()
    await db.refresh(bet_row)
    return JSONResponse({"bet": _bet_to_dict(bet_row), "bank": new_bank})


@router.delete("/bet/{bet_id}")
async def delete_bet(
    bet_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    user_id, session_id = _identity(request, user)

    if user_id:
        q = select(PaperBetModel).where(
            PaperBetModel.bet_id == bet_id,
            PaperBetModel.user_id == user_id,
        )
    else:
        q = select(PaperBetModel).where(
            PaperBetModel.bet_id == bet_id,
            PaperBetModel.session_id == session_id,
        )

    result = await db.execute(q)
    bet_row = result.scalar_one_or_none()
    if not bet_row:
        raise HTTPException(status_code=404, detail="Bet not found")

    # Refund stake if still pending
    if bet_row.status == "pending":
        if user:
            user.bankroll = round(user.bankroll + bet_row.stake, 2)
        else:
            bank = await _get_bank(None, session_id)
            await _set_bank(None, session_id, round(bank + bet_row.stake, 2))

    await db.delete(bet_row)
    await db.commit()
    return JSONResponse({"message": "Bet removed"})


@router.post("/settle/{race_id}")
async def settle(
    race_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    user_id, session_id = _identity(request, user)
    settled, status = await _settle_race_pg(db, user_id, session_id, race_id, user)

    messages = {
        "settled":    f"{len(settled)} bet(s) settled",
        "no_bets":    "No pending bets found for this race",
        "no_results": "Race result not available yet — check back after the race finishes",
        "error":      "Could not fetch results — try again in a moment",
    }
    return JSONResponse({"message": messages[status], "settled": settled})


@router.get("/bets")
async def list_bets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    user_id, session_id = _identity(request, user)
    bets = await _pg_get_bets(db, user_id, session_id)
    return JSONResponse({"bets": bets, "total": len(bets)})


@router.get("/bank")
async def get_bank_balance(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    if user:
        return JSONResponse({"bank": user.bankroll})
    _, session_id = _identity(request, None)
    return JSONResponse({"bank": await _get_bank(None, session_id)})


@router.get("/stats")
async def get_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> JSONResponse:
    user_id, session_id = _identity(request, user)
    bets = await _pg_get_bets(db, user_id, session_id)
    bank = user.bankroll if user else await _get_bank(None, session_id)

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
    user_id, session_id = _identity(request, user)

    if user_id:
        result = await db.execute(select(PaperBetModel).where(PaperBetModel.user_id == user_id))
        for bet_row in result.scalars().all():
            await db.delete(bet_row)
        user.bankroll = INITIAL_BANK
        await db.commit()
    else:
        result = await db.execute(select(PaperBetModel).where(PaperBetModel.session_id == session_id))
        for bet_row in result.scalars().all():
            await db.delete(bet_row)
        await db.commit()
        await _set_bank(None, session_id, INITIAL_BANK)

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

    _, session_id = _identity(request, None)
    bank = await _get_bank(None, session_id)
    new_bank = round(bank + req.amount, 2)
    await _set_bank(None, session_id, new_bank)
    return JSONResponse({"bank": new_bank})
