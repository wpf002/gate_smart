"""
Pick contests — call a race's winner before post, score points, climb the board.

Purely educational. Nothing is wagered, no money is held, and there are no prizes.
Every race still links out to licensed wagering platforms for anyone who wants to
bet for real.
"""
import re
from datetime import date, datetime, timedelta, timezone

import msgspec
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.contest import ContestPick
from app.models.user import User
from app.services.contest import (
    BET_TYPES, DEFAULT_BET_TYPE, POINTS_BEAT_BONUS, POINTS_CORRECT, STAKE,
    beat_secretariat_streak, best_streak, bet_spec, pick_day_streak,
)

router = APIRouter()

_NAME_OK = re.compile(r"^[A-Za-z0-9 _.-]{3,40}$")


class PickRequest(msgspec.Struct):
    race_id: str
    horse_name: str = ""
    program_number: str = ""
    bet_type: str = DEFAULT_BET_TYPE
    # Horses in finish order. A straight bet takes one; an exacta two, a
    # trifecta three. `horse_name` alone is still accepted so older clients
    # keep working.
    horses: list[str] = msgspec.field(default_factory=list)


class NameRequest(msgspec.Struct):
    display_name: str


def _public_name(user_id: int, display_name) -> str:
    return display_name or f"Handicapper {user_id}"


def _race_off(race: dict):
    """The race's scheduled post time as an aware datetime, or None."""
    raw = race.get("off_dt")
    if not raw:
        return None
    try:
        off = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return off if off.tzinfo else off.replace(tzinfo=timezone.utc)


def _pick_json(p: ContestPick) -> dict:
    """One pick as the client sees it, including what $2 on it returned."""
    bet_type = p.bet_type or "win"
    return {
        "race_id": p.race_id, "race_date": p.race_date.isoformat() if p.race_date else None,
        "horse_name": p.horse_name, "program_number": p.program_number,
        "bet_type": bet_type, "bet_label": bet_spec(bet_type)["label"],
        "selections": p.selections or [{"name": p.horse_name, "key": p.horse_key,
                                        "number": p.program_number or ""}],
        "settled": p.settled, "winner_name": p.winner_name, "correct": p.correct,
        "secretariat_correct": p.secretariat_correct, "beat_secretariat": p.beat_secretariat,
        "points": p.points, "stake": STAKE, "payoff": p.payoff,
        "net": None if p.payoff is None else round(p.payoff - STAKE, 2),
    }


def _bankroll(picks) -> dict:
    """Flat-$2 P&L across the picks the chart actually priced.

    A pick with no payoff is left out of the denominator rather than counted as
    a loss — the same rule the Report Card uses for Secretariat.
    """
    priced = [p for p in picks if p.payoff is not None]
    staked = STAKE * len(priced)
    returned = sum(p.payoff for p in priced)
    return {
        "bets": len(priced), "unpriced": sum(1 for p in picks if p.settled and p.payoff is None),
        "stake": STAKE, "staked": round(staked, 2), "returned": round(returned, 2),
        "net": round(returned - staked, 2),
        "roi": round((returned - staked) / staked, 4) if staked else None,
        "cashed": sum(1 for p in priced if p.payoff > 0),
        "best": round(max((p.payoff for p in priced), default=0) - STAKE, 2) if priced else None,
    }


@router.post("/picks")
async def make_pick(request: Request, user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    """Call a race's winner. Replaces your earlier call until post time, then locks."""
    try:
        req = msgspec.json.decode(await request.body(), type=PickRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    from app.services import racing_api
    from app.services.horse_form import horse_key

    race = await racing_api.get_race(req.race_id)
    off = _race_off(race)
    if off is None:
        raise HTTPException(status_code=409, detail="This race has no post time, so picks can't be locked fairly")
    if datetime.now(timezone.utc) >= off:
        raise HTTPException(status_code=409, detail="Picks are locked — this race is already off")

    bet_type = (req.bet_type or DEFAULT_BET_TYPE).lower()
    if bet_type not in BET_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown bet type: {req.bet_type}")
    needed = bet_spec(bet_type)["picks"]

    names = [n for n in (req.horses or [req.horse_name]) if n and n.strip()]
    if len(names) != needed:
        raise HTTPException(
            status_code=400,
            detail=f"A {BET_TYPES[bet_type]['label'].lower()} needs {needed} horse"
                   f"{'s' if needed > 1 else ''}, in order",
        )

    by_key = {horse_key(r.get("horse_name", "")): r for r in race.get("runners") or []}
    selections = []
    for name in names:
        runner = by_key.get(horse_key(name))
        if not runner:
            raise HTTPException(status_code=400, detail=f"{name} isn't entered in this race")
        if runner.get("scratched"):
            raise HTTPException(status_code=400, detail=f"{name} is scratched")
        selections.append({
            "name": runner.get("horse_name", "")[:160],
            "key": horse_key(runner.get("horse_name", "")),
            "number": str(runner.get("number") or "")[:10],
        })
    if len({s["key"] for s in selections}) != len(selections):
        raise HTTPException(status_code=400, detail="Each horse can only be used once")

    values = {
        "user_id": user.id,
        "race_id": req.race_id,
        "race_date": off.date(),
        # Selection 1 is mirrored into the flat columns so the leaderboard and
        # every pre-exotics query keep working untouched.
        "horse_name": selections[0]["name"],
        "horse_key": selections[0]["key"],
        "program_number": selections[0]["number"] or req.program_number[:10] or None,
        "bet_type": bet_type,
        "selections": selections,
        "created_at": datetime.now(timezone.utc),
    }
    stmt = pg_insert(ContestPick).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_contest_pick_user_race",
        set_={k: values[k] for k in
              ("horse_name", "horse_key", "program_number", "bet_type", "selections", "created_at")},
    )
    await db.execute(stmt)
    await db.commit()
    return {"race_id": req.race_id, "horse_name": values["horse_name"],
            "program_number": values["program_number"], "bet_type": bet_type,
            "selections": selections, "stake": STAKE, "locks_at": off.isoformat()}


@router.get("/picks")
async def my_picks(race_date: str = "", user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    """Your calls for a day (default today), graded where the result is in.

    With no date, later dates' ungraded calls come back too. A pick made on
    tomorrow's card belongs to tomorrow, and leaving it out was the only way to
    lock one in and then find no trace of it anywhere in the app.
    """
    try:
        day = date.fromisoformat(race_date) if race_date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="race_date must be YYYY-MM-DD")
    where = ContestPick.race_date == day
    if not race_date:
        where = or_(where, and_(ContestPick.race_date > day, ContestPick.settled == False))  # noqa: E712
    rows = (await db.execute(
        select(ContestPick)
        .where(ContestPick.user_id == user.id, where)
        .order_by(ContestPick.race_date, ContestPick.created_at)
    )).scalars().all()
    return {"date": day.isoformat(), "stake": STAKE,
            "picks": [_pick_json(p) for p in rows]}


@router.get("/leaderboard")
async def leaderboard(period: str = "week", db: AsyncSession = Depends(get_db)):
    """Standings by points over today or the last 7 days.

    Secretariat is shown as the bar to beat, as a win rate rather than a points
    total: it calls every race on the card, so its raw points would bury anyone
    who picks a handful.
    """
    if period not in ("day", "week"):
        raise HTTPException(status_code=400, detail="period must be day or week")
    since = date.today() if period == "day" else date.today() - timedelta(days=6)

    rows = (await db.execute(
        select(
            ContestPick.user_id,
            User.display_name,
            func.sum(ContestPick.points).label("points"),
            func.count().label("picks"),
        )
        .join(User, User.id == ContestPick.user_id)
        .where(ContestPick.settled == True, ContestPick.race_date >= since)  # noqa: E712
        .group_by(ContestPick.user_id, User.display_name)
    )).all()

    wins = dict((await db.execute(
        select(ContestPick.user_id, func.count())
        .where(ContestPick.settled == True, ContestPick.correct == True,  # noqa: E712
               ContestPick.race_date >= since)
        .group_by(ContestPick.user_id)
    )).all())
    beats = dict((await db.execute(
        select(ContestPick.user_id, func.count())
        .where(ContestPick.settled == True, ContestPick.beat_secretariat == True,  # noqa: E712
               ContestPick.race_date >= since)
        .group_by(ContestPick.user_id)
    )).all())

    board = sorted(
        ({"name": _public_name(uid, dn), "points": int(pts or 0), "picks": n,
          "wins": wins.get(uid, 0), "win_rate": round(wins.get(uid, 0) / n, 3) if n else 0,
          "beat_secretariat": beats.get(uid, 0), "user_id": uid}
         for uid, dn, pts, n in rows),
        key=lambda r: (-r["points"], -r["win_rate"], r["picks"]),
    )
    for i, row in enumerate(board, 1):
        row["rank"] = i

    # The bar to beat is a fixed 30-day benchmark, not a window that moves with
    # the toggle. On "Today" it used to read from races that hadn't been graded
    # yet and vanish; on "This Week" it was reading four usable days, one of
    # them capped at 40 races and one with no picks at all.
    from app.api.routes.ai_advisor import ACCURACY_WINDOW_DAYS
    from app.models.accuracy import RacePrediction
    bar_since = date.today() - timedelta(days=ACCURACY_WINDOW_DAYS - 1)
    s = (await db.execute(
        select(func.count(), func.sum(case((RacePrediction.top_pick_correct == True, 1), else_=0)))  # noqa: E712
        .where(RacePrediction.analysis_mode == "auto_daily", RacePrediction.user_id.is_(None),
               RacePrediction.result_fetched == True, RacePrediction.race_date >= bar_since)  # noqa: E712
    )).one()
    return {
        "period": period,
        "since": since.isoformat(),
        "scoring": {"correct_winner": POINTS_CORRECT, "beat_secretariat_bonus": POINTS_BEAT_BONUS,
                    "bet_types": {k: {"label": v["label"], "points": v["points"], "picks": v["picks"]}
                                  for k, v in BET_TYPES.items()}},
        "secretariat": {"races": s[0] or 0, "days": ACCURACY_WINDOW_DAYS,
                        "win_rate": round((s[1] or 0) / s[0], 3) if s[0] else None},
        "board": [{k: v for k, v in r.items() if k != "user_id"} for r in board[:100]],
    }


@router.get("/me")
async def my_progress(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Your streaks and running totals."""
    rows = list((await db.execute(
        select(ContestPick).where(ContestPick.user_id == user.id).order_by(ContestPick.race_date, ContestPick.created_at)
    )).scalars().all())
    settled = [{"correct": p.correct, "beat_secretariat": p.beat_secretariat} for p in rows if p.settled]
    return {
        "display_name": _public_name(user.id, user.display_name),
        "pick_day_streak": pick_day_streak((p.race_date for p in rows), date.today()),
        "beat_secretariat_streak": beat_secretariat_streak(settled),
        "best_correct_streak": best_streak([bool(p["correct"]) for p in settled]),
        "total_picks": len(rows),
        "settled": len(settled),
        "wins": sum(1 for p in settled if p["correct"]),
        "beat_secretariat": sum(1 for p in settled if p["beat_secretariat"]),
        "points": sum(p.points for p in rows),
        # What flat $2 on every call would have done. No money moves; this is
        # the same scorekeeping figure the Report Card publishes for Secretariat.
        "bankroll": _bankroll(rows),
        "bankroll_today": _bankroll([p for p in rows if p.race_date == date.today()]),
    }


@router.put("/display-name")
async def set_display_name(request: Request, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    """The name shown on the leaderboard. 3-40 letters, numbers, spaces, _ . -"""
    try:
        req = msgspec.json.decode(await request.body(), type=NameRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")
    name = req.display_name.strip()
    if not _NAME_OK.match(name):
        raise HTTPException(status_code=400, detail="Use 3-40 letters, numbers, spaces, _ . or -")
    taken = (await db.execute(
        select(User.id).where(func.lower(User.display_name) == name.lower(), User.id != user.id)
    )).first()
    if taken:
        raise HTTPException(status_code=409, detail="That name is taken")
    db_user = await db.get(User, user.id)
    db_user.display_name = name
    await db.commit()
    return {"display_name": name}
