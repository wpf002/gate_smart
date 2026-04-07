import uuid
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.cache import cache_get, cache_set
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


class TopupRequest(msgspec.Struct):
    amount: float


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _get_session(request: Request) -> str:
    sid = request.headers.get("X-Session-ID", "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    return sid


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


# ── Settle logic (shared with auto-settle hook) ────────────────────────────────

async def settle_race_bets(sid: str, race_id: str) -> list:
    """
    Fetch today's results, find the race, and settle all pending bets.
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

        runner = runners_by_id.get(bet["horse_id"]) or runners_by_name.get(
            bet["horse_name"].lower()
        )

        if not runner:
            bet["status"] = "void"
            bet["returns"] = bet["stake"]
            bet["pnl"] = 0.0
            bet["settled_at"] = datetime.now(timezone.utc).isoformat()
            bank += bet["stake"]
            settled_bets.append(bet)
            continue

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
        bank += returns
        settled_bets.append(bet)

    await _set_bank(sid, round(bank, 2))
    await _set_bets(sid, bets)
    return settled_bets


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/bet")
async def place_bet(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=PlaceBetRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    sid = _get_session(request)

    if req.stake <= 0:
        raise HTTPException(status_code=400, detail="stake must be positive")

    bank = await _get_bank(sid)
    if req.stake > bank:
        raise HTTPException(
            status_code=400, detail=f"insufficient funds (bank: £{bank:.2f})"
        )

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
    }

    new_bank = round(bank - req.stake, 2)
    await _set_bank(sid, new_bank)

    bets = await _get_bets(sid)
    bets.append(bet)
    await _set_bets(sid, bets)

    return JSONResponse({"bet": bet, "bank": new_bank})


@router.post("/settle/{race_id}")
async def settle(race_id: str, request: Request) -> JSONResponse:
    sid = _get_session(request)
    settled = await settle_race_bets(sid, race_id)
    if not settled:
        return JSONResponse({"message": "no pending bets found for this race", "settled": []})
    return JSONResponse({"message": f"{len(settled)} bet(s) settled", "settled": settled})


@router.get("/bets")
async def list_bets(request: Request) -> JSONResponse:
    sid = _get_session(request)
    bets = await _get_bets(sid)
    return JSONResponse({"bets": list(reversed(bets)), "total": len(bets)})


@router.get("/bank")
async def get_bank_balance(request: Request) -> JSONResponse:
    sid = _get_session(request)
    bank = await _get_bank(sid)
    return JSONResponse({"bank": bank})


@router.get("/stats")
async def get_stats(request: Request) -> JSONResponse:
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
async def reset(request: Request) -> JSONResponse:
    sid = _get_session(request)
    await _set_bank(sid, INITIAL_BANK)
    await _set_bets(sid, [])
    return JSONResponse({"bank": INITIAL_BANK, "message": "Simulator reset to £500"})


@router.post("/bank/topup")
async def topup(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=TopupRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    if req.amount <= 0 or req.amount > 10000:
        raise HTTPException(status_code=400, detail="amount must be 1–10000")

    sid = _get_session(request)
    bank = await _get_bank(sid)
    new_bank = round(bank + req.amount, 2)
    await _set_bank(sid, new_bank)
    return JSONResponse({"bank": new_bank})
