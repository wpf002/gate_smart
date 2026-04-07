import json
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.cache import cache_get, cache_set
from app.services import racing_api, secretariat

router = APIRouter()


class AnalyzeRequest(msgspec.Struct):
    race_id: str
    mode: str = "balanced"
    bankroll: Optional[float] = None


class RecommendRequest(msgspec.Struct):
    race_id: str
    bankroll: float
    risk_tolerance: str = "medium"
    experience_level: str = "beginner"


class AskRequest(msgspec.Struct):
    question: str
    context: Optional[dict] = None


class ExplainFormRequest(msgspec.Struct):
    form_string: str
    horse_name: str = ""


class ScoreCardRequest(msgspec.Struct):
    race_id: str
    bankroll: Optional[float] = None


@router.post("/analyze")
async def analyze_race(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AnalyzeRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    cache_key = f"ai_analysis:{req.race_id}:{req.mode}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc

    try:
        analysis = await secretariat.analyze_race(race_data, mode=req.mode, bankroll=req.bankroll)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI analysis error: {exc}") from exc

    await cache_set(cache_key, analysis, ex=300)
    return JSONResponse(analysis)


@router.post("/recommend-bet")
async def recommend_bet(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=RecommendRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc

    try:
        analysis = await secretariat.analyze_race(race_data, mode="balanced")
        recommendation = await secretariat.recommend_bet_type(
            req.bankroll, req.risk_tolerance, req.experience_level, analysis
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI error: {exc}") from exc

    return JSONResponse(recommendation)


@router.post("/ask")
async def ask(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AskRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    try:
        answer = await secretariat.answer_betting_question(req.question, req.context)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI error: {exc}") from exc

    return JSONResponse({"answer": answer})


@router.post("/analyze/stream")
async def analyze_race_stream(request: Request) -> StreamingResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AnalyzeRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    cache_key = f"ai_analysis:{req.race_id}:{req.mode}"

    async def generate():
        try:
            cached = await cache_get(cache_key)
            if cached is not None:
                yield f"data: {json.dumps({'result': cached})}\n\n"
                yield "data: [DONE]\n\n"
                return

            try:
                race_data = await racing_api.get_race(req.race_id)
            except Exception as exc:
                yield f"data: {json.dumps({'error': f'Racing API error: {exc}'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            result = None
            async for event_type, data in secretariat.stream_analyze_race(
                race_data, mode=req.mode, bankroll=req.bankroll
            ):
                if event_type == "chunk":
                    yield f"data: {json.dumps({'t': data})}\n\n"
                elif event_type == "result":
                    result = data

            if result:
                await cache_set(cache_key, result, ex=300)
                yield f"data: {json.dumps({'result': result})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/scorecard")
async def score_card(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=ScoreCardRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    cache_key = f"scorecard:{req.race_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc

    try:
        result = await secretariat.score_race(race_data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI scoring error: {exc}") from exc

    await cache_set(cache_key, result, ex=600)
    return JSONResponse(result)


@router.post("/explain-form")
async def explain_form(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=ExplainFormRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    if not req.form_string:
        raise HTTPException(status_code=400, detail="form_string is required")

    try:
        result = await secretariat.explain_form_string(req.form_string, req.horse_name or req.form_string)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI error: {exc}") from exc

    return JSONResponse(result)
