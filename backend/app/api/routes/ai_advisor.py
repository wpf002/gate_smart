from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/analyze")
async def analyze_race(request: Request):
    return {"error": "Racing API not configured"}


@router.post("/recommend-bet")
async def recommend_bet(request: Request):
    return {"error": "Racing API not configured"}


@router.post("/ask")
async def ask(request: Request):
    return {"answer": ""}
