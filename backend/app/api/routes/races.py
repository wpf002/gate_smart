import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.cache import cache_get, cache_incr, cache_set
from app.services import racing_api

router = APIRouter()


async def _settle_predictions(race_ids: list[str]) -> None:
    """Check pending predictions against NA results and update accuracy counters."""
    for race_id in race_ids:
        try:
            pred = await cache_get(f"predictions:{race_id}")
            if not pred or pred.get("status") != "pending":
                continue

            results_data = await racing_api.get_na_results_full()
            race_result = next(
                (r for r in results_data.get("results", []) if r.get("race_id") == race_id),
                None,
            )
            if not race_result:
                continue

            winner = next(
                (r for r in race_result.get("runners", []) if str(r.get("position", "")) == "1"),
                None,
            )
            if not winner:
                continue

            winner_id = winner.get("horse_id", "")
            winner_name = winner.get("horse_name") or winner.get("horse", "")
            correct = winner_id and winner_id == pred.get("top_pick_horse_id")

            pred["status"] = "correct" if correct else "incorrect"
            pred["actual_winner"] = winner_name
            pred["settled_at"] = datetime.now(timezone.utc).isoformat()
            await cache_set(f"predictions:{race_id}", pred, ex=604800)

            await cache_incr("accuracy:total")
            if correct:
                await cache_incr("accuracy:correct")
        except Exception:
            continue


@router.get("/today")
async def races_today(region: str = None):
    try:
        return await racing_api.get_na_racecards_full()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/results/race/{race_id}")
async def results_for_race(race_id: str):
    """Return finishing order for a single NA race. Race IDs use '{meet_id}-{race_number}' format."""
    for attempt in range(2):
        try:
            if "-" in race_id:
                meet_id, race_number = race_id.rsplit("-", 1)
                meet_results = await racing_api.get_na_meet_results(meet_id)
                for race in meet_results.get("races", []):
                    rk = race.get("race_key") or {}
                    rnum = str(rk.get("race_number", "")) if isinstance(rk, dict) else ""
                    if rnum == str(race_number):
                        # NA results endpoint returns runners as the top-3
                        # finishers in finish order, with no explicit position
                        # field. Fall back to (index + 1) so the result card
                        # shows actual finish positions.
                        runners = []
                        for idx, e in enumerate(race.get("runners", [])):
                            explicit = (
                                e.get("official_finish_position")
                                or e.get("finish_position")
                            )
                            position = str(explicit) if explicit else str(idx + 1)
                            runners.append({
                                "horse_id": str(e.get("registration_number", "")),
                                "horse_name": e.get("horse_name", ""),
                                "position": position,
                                "sp": str(e.get("final_odds") or e.get("morning_line_odds", "SP")),
                                "number": str(e.get("program_number", "")),
                            })
                        if runners:
                            return {"race_id": race_id, "title": race.get("race_name", ""), "runners": runners}
        except Exception:
            pass
        if attempt == 0:
            await asyncio.sleep(1)
    raise HTTPException(status_code=404, detail="Results not yet available")


@router.get("/results/today")
async def results_today(request: Request, background_tasks: BackgroundTasks, region: str = None):
    try:
        data = await racing_api.get_na_results_full()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    sid = request.headers.get("X-Session-ID", "").strip()
    race_ids = [r.get("race_id") for r in data.get("results", []) if r.get("race_id")]

    if sid:
        from app.api.routes.simulator import settle_race_bets
        for rid in race_ids:
            background_tasks.add_task(settle_race_bets, sid, rid)

    if race_ids:
        background_tasks.add_task(_settle_predictions, race_ids)

    return data


@router.get("/results/{result_date}")
async def results_by_date(result_date: str, region: str = None):
    try:
        return await racing_api.get_na_results_full(date=result_date)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/date/{race_date}")
async def races_by_date(race_date: str, region: str = None):
    try:
        return await racing_api.get_na_racecards_full(date=race_date)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/ticket/{race_id}")
async def race_ticket(race_id: str):
    """Secretariat's betting ticket for a race, graded against the official chart.

    Before the race it explains what to bet. After, each leg shows whether it hit
    and what $2 actually returned. Nothing is estimated: legs without an official
    price come back "unpriced".
    """
    from sqlalchemy import select

    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from app.services.horse_form import horse_key
    from app.services.ticket import build_ticket, grade_ticket, ticket_summary

    async with _db._AsyncSessionLocal() as db:
        pred = (await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_id == race_id,
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.user_id.is_(None),
            )
        )).scalars().first()
    if not pred:
        raise HTTPException(status_code=404, detail="No Secretariat pick for this race yet")

    names = [pred.predicted_first, pred.predicted_second, pred.predicted_third]
    numbers: dict[str, str] = {}
    try:
        race = await racing_api.get_race(race_id)
        numbers = {horse_key(r.get("horse_name", "")): r.get("number") for r in race.get("runners") or []}
    except Exception:
        race = {}
    if pred.predicted_first_num and horse_key(pred.predicted_first) not in numbers:
        numbers[horse_key(pred.predicted_first)] = pred.predicted_first_num

    race_number = race_id.rsplit("-", 1)[-1] if "-" in race_id else None
    picks = [{"name": n, "number": numbers.get(horse_key(n))} for n in names if n]
    legs = build_ticket(picks, race_number)

    # Graded from the live results chart rather than waiting on the nightly
    # accuracy job, so the slip turns green or red the same afternoon.
    settled = False
    if "-" in race_id:
        try:
            meet = await racing_api.get_na_meet_results(race_id.rsplit("-", 1)[0])
            result = next(
                (r for r in meet.get("races", [])
                 if str((r.get("race_key") or {}).get("race_number", "")) == str(race_number)),
                None,
            )
            if result and result.get("runners"):
                legs = grade_ticket(legs, result)
                settled = True
        except Exception:
            pass

    return {
        "race_id": race_id,
        "settled": settled,
        "legs": legs,
        "summary": ticket_summary(legs) if settled else None,
    }


@router.get("/{race_id}")
async def race_detail(race_id: str):
    try:
        return await racing_api.get_race(race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")
