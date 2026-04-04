from fastapi import APIRouter

router = APIRouter()


@router.post("/odds/convert")
async def convert_odds(body: dict):
    return {}


@router.get("/types")
async def bet_types():
    return {"types": []}


@router.post("/payout/calculate")
async def calculate_payout(body: dict):
    return {}
