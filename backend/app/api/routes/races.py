from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.services import racing_api

router = APIRouter()


@router.get("/today")
async def races_today(region: str = None):
    try:
        return await racing_api.get_racecards(region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/results/today")
async def results_today(request: Request, background_tasks: BackgroundTasks, region: str = None):
    try:
        data = await racing_api.get_results(region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc

    # Auto-settle any pending paper bets for races that now have results
    sid = request.headers.get("X-Session-ID", "").strip()
    if sid:
        from app.api.routes.simulator import settle_race_bets
        race_ids = [r.get("race_id") for r in data.get("results", []) if r.get("race_id")]
        for rid in race_ids:
            background_tasks.add_task(settle_race_bets, sid, rid)

    return data


@router.get("/results/{result_date}")
async def results_by_date(result_date: str, region: str = None):
    try:
        return await racing_api.get_results(date=result_date, region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/date/{race_date}")
async def races_by_date(race_date: str, region: str = None):
    try:
        return await racing_api.get_racecards(date=race_date, region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/{race_id}")
async def race_detail(race_id: str):
    try:
        return await racing_api.get_race(race_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc
