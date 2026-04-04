from fastapi import APIRouter, HTTPException

from app.services import racing_api

router = APIRouter()


@router.get("/today")
async def races_today(region: str = "gb"):
    try:
        return await racing_api.get_racecards(region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/results/today")
async def results_today(region: str = "gb"):
    try:
        return await racing_api.get_results(region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/results/{result_date}")
async def results_by_date(result_date: str, region: str = "gb"):
    try:
        return await racing_api.get_results(date=result_date, region=region)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/date/{race_date}")
async def races_by_date(race_date: str, region: str = "gb"):
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
