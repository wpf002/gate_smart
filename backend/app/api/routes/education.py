from fastapi import APIRouter

router = APIRouter()


@router.get("/glossary")
async def glossary():
    return {"terms": []}


@router.get("/beginner-guide")
async def beginner_guide():
    return {"sections": []}


@router.get("/bankroll-guide")
async def bankroll_guide():
    return {"sections": []}
