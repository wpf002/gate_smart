from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.services import racing_api
from app.core.cache import cache_get, cache_set, cache_incr

router = APIRouter()


def _is_usa_region(region: str) -> bool:
    """Return True if the request targets North American tracks."""
    return bool(region and "usa" in region.lower())


async def _settle_predictions(race_ids: list[str]) -> None:
    """Check pending predictions against results and update accuracy counters."""
    for race_id in race_ids:
        try:
            pred = await cache_get(f"predictions:{race_id}")
            if not pred or pred.get("status") != "pending":
                continue

            results_data = await racing_api.get_results()
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
        if _is_usa_region(region):
            return await racing_api.get_na_racecards_full()
        return await racing_api.get_racecards(region=region)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/results/today")
async def results_today(request: Request, background_tasks: BackgroundTasks, region: str = None):
    try:
        if _is_usa_region(region):
            data = await racing_api.get_na_results_full()
        else:
            data = await racing_api.get_results(region=region)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    # Auto-settle paper bets and predictions for races with results
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
        if _is_usa_region(region):
            return await racing_api.get_na_results_full(date=result_date)
        return await racing_api.get_results(date=result_date, region=region)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/date/{race_date}")
async def races_by_date(race_date: str, region: str = None):
    try:
        if _is_usa_region(region):
            return await racing_api.get_na_racecards_full(date=race_date)
        return await racing_api.get_racecards(date=race_date, region=region)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")


@router.get("/{race_id}")
async def race_detail(race_id: str):
    try:
        return await racing_api.get_race(race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")
