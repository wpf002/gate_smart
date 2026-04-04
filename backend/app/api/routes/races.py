from fastapi import APIRouter

router = APIRouter()


@router.get("/today")
async def races_today(region: str = "gb"):
    return {"races": [], "region": region}


@router.get("/date/{date}")
async def races_by_date(date: str, region: str = "gb"):
    return {"races": [], "date": date, "region": region}


@router.get("/results/today")
async def results_today(region: str = "gb"):
    return {"results": [], "region": region}


@router.get("/{race_id}")
async def race_detail(race_id: str):
    return {"race_id": race_id, "runners": []}
