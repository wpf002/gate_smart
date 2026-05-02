import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.cache import cache_get, cache_set, cache_incr
from app.core.limiter import limiter
from app.services import racing_api, secretariat

router = APIRouter()

RACE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+$')


def _validate_race_id(race_id: str) -> None:
    if not race_id or not RACE_ID_PATTERN.match(race_id):
        raise HTTPException(status_code=400, detail="Invalid race_id")


class AnalyzeRequest(msgspec.Struct):
    race_id: str
    mode: str = "balanced"
    bankroll: Optional[float] = None
    experience_level: Optional[str] = None


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


class DebriefRequest(msgspec.Struct):
    race_id: str


@router.post("/analyze")
@limiter.limit("10/minute")
async def analyze_race(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AnalyzeRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    _validate_race_id(req.race_id)

    cache_key = f"ai_analysis:{req.race_id}:{req.mode}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    try:
        analysis = await secretariat.analyze_race(race_data, mode=req.mode, bankroll=req.bankroll)
    except secretariat.SecretariatBusyError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        # If the field is large, retry with top-8 runners by odds
        runners = race_data.get("runners", [])
        if len(runners) > 10:
            def _odds_key(r):
                odds = r.get("odds", "") or ""
                try:
                    if "/" in str(odds):
                        n, d = str(odds).split("/")
                        return int(n) / int(d)
                    return float(odds)
                except Exception:
                    return 9999
            trimmed = sorted(runners, key=_odds_key)[:8]
            race_data_trimmed = {**race_data, "runners": trimmed}
            try:
                analysis = await secretariat.analyze_race(
                    race_data_trimmed, mode=req.mode, bankroll=req.bankroll
                )
            except Exception:
                raise HTTPException(
                    status_code=502,
                    detail="This race has too many runners for full analysis. Secretariat will analyse the top 8 contenders — try again.",
                )
        else:
            raise HTTPException(status_code=502, detail="AI analysis unavailable")

    await cache_set(cache_key, analysis, ex=300)
    await _store_prediction(race_data, analysis)
    return JSONResponse(analysis)


@router.post("/recommend-bet")
async def recommend_bet(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=RecommendRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    _validate_race_id(req.race_id)

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    try:
        analysis = await secretariat.analyze_race(race_data, mode="balanced")
        recommendation = await secretariat.recommend_bet_type(
            req.bankroll, req.risk_tolerance, req.experience_level, analysis
        )
    except Exception:
        raise HTTPException(status_code=502, detail="AI analysis unavailable")

    return JSONResponse(recommendation)


@router.post("/ask")
@limiter.limit("30/minute")
async def ask(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AskRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    if len(req.question) > 500:
        raise HTTPException(status_code=400, detail="Question too long (max 500 characters)")

    try:
        answer = await secretariat.answer_betting_question(req.question, req.context)
    except Exception:
        raise HTTPException(status_code=502, detail="AI analysis unavailable")

    return JSONResponse({"answer": answer})


@router.post("/analyze/stream")
@limiter.limit("10/minute")
async def analyze_race_stream(request: Request) -> StreamingResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=AnalyzeRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    _validate_race_id(req.race_id)

    cache_key = f"ai_analysis:{req.race_id}:{req.mode}"

    # Extract optional user_id from JWT for per-user prediction tracking
    _user_id = None
    try:
        _auth_header = request.headers.get("Authorization", "")
        if _auth_header.startswith("Bearer "):
            from app.core.auth import decode_token
            _user_id = decode_token(_auth_header[7:])
    except Exception:
        pass

    async def generate():
        try:
            cached = await cache_get(cache_key)
            if cached is not None:
                yield f"data: {json.dumps({'result': cached})}\n\n"
                yield "data: [DONE]\n\n"
                return

            try:
                race_data = await racing_api.get_race(req.race_id)
            except Exception:
                yield f"data: {json.dumps({'error': 'Racing data unavailable'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            result = None
            async for event_type, data in secretariat.stream_analyze_race(
                race_data, mode=req.mode, bankroll=req.bankroll, user_id=_user_id,
                experience_level=req.experience_level,
            ):
                if event_type == "chunk":
                    yield f"data: {json.dumps({'t': data})}\n\n"
                elif event_type == "result":
                    result = data

            if result:
                await cache_set(cache_key, result, ex=300)
                try:
                    await secretariat.extract_and_store_fair_prices(req.race_id, result)
                except Exception:
                    pass
                try:
                    await _store_prediction(race_data, result)
                except Exception:
                    pass
                yield f"data: {json.dumps({'result': result})}\n\n"

        except Exception:
            yield f"data: {json.dumps({'error': 'An unexpected error occurred'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/scorecard")
@limiter.limit("10/minute")
async def score_card(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=ScoreCardRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    _validate_race_id(req.race_id)

    cache_key = f"scorecard:{req.race_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    try:
        result = await secretariat.score_race(race_data)
    except Exception:
        raise HTTPException(status_code=502, detail="AI scoring unavailable")

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
    except Exception:
        raise HTTPException(status_code=502, detail="AI analysis unavailable")

    return JSONResponse(result)


async def _find_race_result(race_id: str) -> dict | None:
    """
    Find results for a race by ID, handling both UK/IRE and NA races.
    NA race IDs use the format "{meet_id}-{race_number}".
    Tries up to 3 times with 2-second delays.
    """
    for attempt in range(3):
        try:
            if "-" in race_id:
                # NA race — extract meet_id and race_number
                meet_id, race_number = race_id.rsplit("-", 1)
                meet_results = await racing_api.get_na_meet_results(meet_id)
                races = meet_results.get("races", [])
                for race in races:
                    race_key = race.get("race_key") or {}
                    rnum = str(race_key.get("race_number", "")) if isinstance(race_key, dict) else ""
                    if rnum == str(race_number):
                        # The NA results endpoint returns the runners array as the
                        # top-3 finishers in finish order, with no explicit position
                        # field. Fall back to (index + 1) so we can surface results.
                        runners = []
                        for idx, entry in enumerate(race.get("runners", [])):
                            explicit = (
                                entry.get("official_finish_position")
                                or entry.get("finish_position")
                            )
                            position = str(explicit) if explicit else str(idx + 1)
                            runners.append({
                                "horse_id": str(entry.get("registration_number", "")),
                                "horse_name": entry.get("horse_name", ""),
                                "horse": entry.get("horse_name", ""),
                                "position": position,
                                "sp": str(entry.get("final_odds") or entry.get("morning_line_odds", "SP")),
                                "number": str(entry.get("program_number", "")),
                            })
                        if runners:
                            return {
                                "race_id": race_id,
                                "runners": runners,
                                "title": race.get("race_name", ""),
                            }
            else:
                # UK/IRE race
                results_data = await racing_api.get_results()
                found = next(
                    (r for r in results_data.get("results", []) if r.get("race_id") == race_id),
                    None,
                )
                if found:
                    return found
        except Exception:
            pass

        if attempt < 2:
            await asyncio.sleep(2)

    return None


@router.post("/debrief")
@limiter.limit("20/minute")
async def race_debrief(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        req = msgspec.json.decode(raw, type=DebriefRequest)
    except Exception:
        raise HTTPException(status_code=400, detail="malformed request body")

    _validate_race_id(req.race_id)

    cached = await cache_get(f"debrief:{req.race_id}")
    if cached is not None:
        return JSONResponse(cached)

    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    race_result = await _find_race_result(req.race_id)

    if not race_result:
        return JSONResponse(
            {
                "status": "pending",
                "message": "Race results are being processed. Try again in 2-3 minutes.",
                "retry_after_seconds": 180,
            },
            status_code=202,
        )

    prior_analysis = await cache_get(f"ai_analysis:{req.race_id}:balanced")

    try:
        result = await secretariat.debrief_race(req.race_id, race_data, race_result, prior_analysis)
    except Exception:
        raise HTTPException(status_code=502, detail="AI debrief unavailable")

    # Settle accuracy tracking asynchronously — fire-and-forget
    asyncio.create_task(_settle_prediction(req.race_id, race_result))

    return JSONResponse(result)


async def _settle_prediction(race_id: str, race_result: dict) -> None:
    """
    Compare stored Secretariat top-pick against the actual race winner and
    update accuracy counters. Safe to call multiple times — checks 'status'.
    """
    try:
        pred = await cache_get(f"predictions:{race_id}")
        if not pred or pred.get("status") != "pending":
            return

        # Find the winner (position == "1")
        runners = race_result.get("runners", [])
        winner = next(
            (r for r in runners if str(r.get("position", "")).strip() == "1"),
            None,
        )
        if not winner:
            return

        actual_winner_id = str(winner.get("horse_id", ""))
        actual_winner_name = winner.get("horse_name", "") or winner.get("horse", "")
        top_pick_id = str(pred.get("top_pick_horse_id", ""))
        top_pick_name = pred.get("top_pick_horse_name", "")

        is_correct = bool(
            top_pick_id and actual_winner_id and top_pick_id == actual_winner_id
        ) or bool(
            top_pick_name and actual_winner_name and
            top_pick_name.strip().lower() == actual_winner_name.strip().lower()
        )

        await cache_incr("accuracy:total")
        if is_correct:
            await cache_incr("accuracy:correct")

        # Mark as settled so we don't double-count
        pred.update({
            "status": "correct" if is_correct else "incorrect",
            "actual_winner": actual_winner_name,
            "actual_winner_id": actual_winner_id,
            "is_correct": is_correct,
            "settled_at": datetime.now(timezone.utc).isoformat(),
        })
        await cache_set(f"predictions:{race_id}", pred, ex=604800)
    except Exception:
        pass  # Never raise — accuracy is non-critical


@router.delete("/analysis/{race_id}")
async def clear_race_analysis(race_id: str) -> JSONResponse:
    """Clear cached analysis and scorecard for a race (used by the Reset button)."""
    _validate_race_id(race_id)
    from app.core.cache import cache_keys, cache_delete
    keys = await cache_keys(f"ai_analysis:{race_id}:*")
    keys += await cache_keys(f"scorecard:{race_id}")
    for key in keys:
        await cache_delete(key)
    return JSONResponse({"cleared": True, "keys_removed": len(keys)})


@router.get("/accuracy")
async def secretariat_accuracy() -> JSONResponse:
    total = int(await cache_get("accuracy:total") or 0)
    correct = int(await cache_get("accuracy:correct") or 0)

    if total == 0:
        return JSONResponse({
            "total_predictions": 0,
            "correct_predictions": 0,
            "win_rate_percent": None,
            "sample_size_note": "No settled races yet",
            "last_updated": None,
        })

    win_rate = round((correct / total) * 100, 1)
    return JSONResponse({
        "total_predictions": total,
        "correct_predictions": correct,
        "win_rate_percent": win_rate,
        "sample_size_note": "Based on settled races since launch",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    })


async def _store_prediction(race_data: dict, analysis: dict) -> None:
    """Store the top pick from an analysis for later accuracy tracking."""
    try:
        runners = analysis.get("runners", [])
        if not runners:
            return
        top_runner = max(runners, key=lambda r: r.get("contender_score", 0), default=None)
        if not top_runner:
            return
        pred = {
            "race_id": race_data.get("race_id", ""),
            "race_name": race_data.get("title", ""),
            "course": race_data.get("course", ""),
            "date": race_data.get("date", ""),
            "top_pick_horse_id": top_runner.get("horse_id", ""),
            "top_pick_horse_name": top_runner.get("horse_name", ""),
            "top_pick_odds": top_runner.get("fair_odds", ""),
            "predicted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "actual_winner": None,
            "settled_at": None,
        }
        race_id = race_data.get("race_id", "")
        if race_id:
            await cache_set(f"predictions:{race_id}", pred, ex=604800)
    except Exception:
        pass
