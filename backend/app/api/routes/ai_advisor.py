import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import msgspec
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

log = logging.getLogger(__name__)

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
    history: Optional[list[dict]] = None


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

    # Fetch race data first so we can fingerprint inputs and lock the analysis
    # against drift. Same fingerprint = same cached analysis (regardless of how
    # many times the user clicks). Scratch / jockey change / ML revision = new
    # fingerprint = fresh analysis. Eliminates LLM-sampling noise between clicks.
    try:
        race_data = await racing_api.get_race(req.race_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Racing data unavailable")

    fp = secretariat.compute_input_fingerprint(race_data)
    cache_key = f"ai_analysis:{req.race_id}:{req.mode}:{fp}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

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

    # Stamp lock metadata so the UI can show "locked at HH:MM" and the user
    # knows picks are stable until inputs change.
    from datetime import datetime, timezone
    analysis["locked_at"] = datetime.now(timezone.utc).isoformat()
    analysis["input_fingerprint"] = fp
    # 6h TTL — long enough to outlast a race day, short enough that stale
    # fingerprints get evicted instead of accumulating in Redis forever.
    await cache_set(cache_key, analysis, ex=21600)
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
        answer = await secretariat.answer_betting_question(req.question, req.context, req.history)
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
            # Fetch race data first so we can fingerprint inputs and lock the
            # cached analysis to those inputs (eliminates LLM-sampling drift
            # between clicks; only re-analyzes when scratches / jockey changes /
            # ML revisions actually shift the inputs).
            try:
                race_data = await racing_api.get_race(req.race_id)
            except Exception:
                yield f"data: {json.dumps({'error': 'Racing data unavailable'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            fp = secretariat.compute_input_fingerprint(race_data)
            cache_key = f"ai_analysis:{req.race_id}:{req.mode}:{fp}"

            cached = await cache_get(cache_key)
            if cached is not None:
                yield f"data: {json.dumps({'result': cached})}\n\n"
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
                from datetime import datetime, timezone
                result["locked_at"] = datetime.now(timezone.utc).isoformat()
                result["input_fingerprint"] = fp
                # 6h TTL — outlasts a race day, prevents stale-fingerprint Redis bloat
                await cache_set(cache_key, result, ex=21600)
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
            log.exception("analyze_race_stream failed for race_id=%s mode=%s", req.race_id, req.mode)
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


@router.get("/morning-line/{race_id}")
async def morning_line(race_id: str) -> JSONResponse:
    """Returns Secretariat's pre-race top-4 picks (predicted finish order) for
    the given race as program numbers — populated nightly by
    nightly_predict_all.py. The on-card "SECRETARIAT'S MORNING LINE" panel
    reads this; no LLM call (data is already in the DB)."""
    _validate_race_id(race_id)

    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from sqlalchemy import select

    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_id == race_id,
                RacePrediction.user_id == None,  # noqa: E711  global auto-prediction row
                RacePrediction.analysis_mode == "auto_daily",
            ).limit(1)
        )
        prediction = result.scalar_one_or_none()

    if prediction is None:
        return JSONResponse({"picks": None, "available": False})

    # Only `predicted_first_num` is stored as a program number; the others
    # are stored as horse names. Cross-reference with the racecard to map
    # names → program numbers for the N-N-N-N display.
    try:
        race_data = await racing_api.get_race(race_id)
    except Exception:
        race_data = {"runners": []}

    def _norm(name: str) -> str:
        return (name or "").lower().strip().replace("'", "").replace("-", " ")

    runner_lookup: dict[str, str] = {}
    for r in race_data.get("runners") or []:
        name = r.get("horse") or r.get("horse_name") or ""
        num = r.get("number") or r.get("program_number") or r.get("cloth_number") or ""
        if name and num:
            runner_lookup[_norm(name)] = str(num).lstrip("#").strip()

    def _num_for(name: str | None, fallback: str | None = None) -> str | None:
        if not name:
            return fallback.lstrip("#").strip() if fallback else None
        return runner_lookup.get(_norm(name)) or (
            fallback.lstrip("#").strip() if fallback else None
        )

    picks = [
        _num_for(prediction.predicted_first, prediction.predicted_first_num),
        _num_for(prediction.predicted_second),
        _num_for(prediction.predicted_third),
        _num_for(prediction.predicted_fourth),
    ]

    return JSONResponse({
        "picks": picks,
        "available": any(p is not None for p in picks),
        "post_time_et": prediction.post_time_et,
    })


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
                            jockey = " ".join(filter(None, [
                                entry.get("jockey_first_name"), entry.get("jockey_last_name")
                            ])).strip()
                            trainer = " ".join(filter(None, [
                                entry.get("trainer_first_name"), entry.get("trainer_last_name")
                            ])).strip()
                            runners.append({
                                "horse_id": str(entry.get("registration_number", "")),
                                "horse_name": entry.get("horse_name", ""),
                                "horse": entry.get("horse_name", ""),
                                "position": position,
                                "sp": str(entry.get("final_odds") or entry.get("morning_line_odds", "SP")),
                                "number": str(entry.get("program_number", "")),
                                "jockey": jockey,
                                "trainer": trainer,
                                "win_payoff": entry.get("win_payoff"),
                                "place_payoff": entry.get("place_payoff"),
                                "show_payoff": entry.get("show_payoff"),
                            })
                        if runners:
                            return {
                                "race_id": race_id,
                                "runners": runners,
                                "title": race.get("race_name", ""),
                                # Rich post-race fields used by the deterministic debrief.
                                "race_class": race.get("race_type_description") or race.get("race_class", ""),
                                "distance_description": race.get("distance_description", ""),
                                "surface_description": race.get("surface_description", ""),
                                "track_condition_description": race.get("track_condition_description", ""),
                                "track_name": race.get("track_name", ""),
                                "total_purse": race.get("total_purse"),
                                "winning_time": (race.get("fraction") or {}).get("winning_time", {}).get("time_in_hundredths"),
                                "fractions_raw": race.get("fraction") or {},
                                "payoffs": race.get("payoffs") or [],
                                "also_ran": race.get("also_ran") or [],
                                "scratches": race.get("scratches") or [],
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

    # v2 cache key: schema changed from LLM-generated narrative to a
    # deterministic facts-only chart. Bumping the prefix invalidates
    # stale v1 entries instead of trying to migrate them.
    cached = await cache_get(f"debrief:v2:{req.race_id}")
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
    """Secretariat top-pick performance over the last 100 settled races.

    All three rates describe the SAME horse (Secretariat's #1 pick):
      win_rate_percent   — top pick finished 1st        (top_pick_correct)
      place_rate_percent — top pick finished top 2      (computed at query time)
      show_rate_percent  — top pick finished top 3      (in_the_money)

    Place isn't stored as a flag — the only "top pick top 2" check is
    derived by comparing predicted_first to actual_first/_second using
    the same name normalization the settler uses.

    Rolling 100-race window. Cached 1h; underlying data refreshes once a
    day via nightly_accuracy.py.
    """
    # Bump the suffix when the payload schema changes so prior deploys'
    # cached payloads can't shadow new fields.
    cache_key = "accuracy:rolling100:v3"
    cached = await cache_get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from sqlalchemy import select

    def _norm(name):
        return (name or "").lower().strip().replace("'", "").replace("-", " ")

    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                RacePrediction.top_pick_correct,
                RacePrediction.in_the_money,
                RacePrediction.predicted_first,
                RacePrediction.actual_first,
                RacePrediction.actual_second,
            )
            .where(
                RacePrediction.result_fetched.is_(True),
                RacePrediction.user_id.is_(None),
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.top_pick_correct.is_not(None),
            )
            .order_by(RacePrediction.settled_at.desc().nulls_last())
            .limit(100)
        )
        rows = result.all()

    total = len(rows)
    wins = sum(1 for r in rows if r.top_pick_correct)
    shows = sum(1 for r in rows if r.in_the_money)
    places = sum(
        1 for r in rows
        if _norm(r.predicted_first)
        and _norm(r.predicted_first) in {_norm(r.actual_first), _norm(r.actual_second)}
    )

    if total == 0:
        payload = {
            "total_predictions": 0,
            "correct_predictions": 0,
            "win_rate_percent": None,
            "place_rate_percent": None,
            "show_rate_percent": None,
            "sample_size_note": "No settled races yet",
            "last_updated": None,
        }
    else:
        payload = {
            "total_predictions": total,
            "correct_predictions": wins,
            "win_rate_percent": round((wins / total) * 100, 1),
            "place_rate_percent": round((places / total) * 100, 1),
            "show_rate_percent": round((shows / total) * 100, 1),
            "sample_size_note": f"Last {total} settled races",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    await cache_set(cache_key, payload, ex=3600)
    return JSONResponse(payload)


@router.get("/accuracy/audit")
async def secretariat_accuracy_audit() -> JSONResponse:
    """Deep audit — for each row in the last-100 sample we compute three
    independent views of the same outcome and surface any disagreement:

      stored_flag  — what nightly_accuracy.py wrote at settle time
      rederived    — recomputed from stored actual_first/_second/_third
      live_api     — fetched fresh from the racing API right now

    Stored == rederived means the math at settle time was right. Stored
    == live_api means the actuals we stored match the source of truth.
    Both equal stored == this metric is honest.
    """
    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from sqlalchemy import select

    def _norm(name):
        return (name or "").lower().strip().replace("'", "").replace("-", " ")

    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction)
            .where(
                RacePrediction.result_fetched.is_(True),
                RacePrediction.user_id.is_(None),
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.top_pick_correct.is_not(None),
            )
            .order_by(RacePrediction.settled_at.desc().nulls_last())
            .limit(100)
        )
        rows = list(result.scalars().all())

    # Re-derive flags from stored actuals — does nightly_accuracy's math hold up?
    stored_match_rederived = {"top": 0, "place": 0, "show": 0, "itm": 0}
    stored_disagreement = []
    for r in rows:
        a1, a2, a3 = _norm(r.actual_first), _norm(r.actual_second), _norm(r.actual_third)
        p1, p2, p3 = _norm(r.predicted_first), _norm(r.predicted_second), _norm(r.predicted_third)
        derived = {
            "top": bool(p1 and p1 == a1),
            "place": bool(p2 and p2 in {a1, a2}),
            "show": bool(p3 and p3 in {a1, a2, a3}),
            "itm": bool(p1 and p1 in {a1, a2, a3}),
        }
        stored_flags = {
            "top": r.top_pick_correct,
            "place": r.place_pick_correct,
            "show": r.show_pick_correct,
            "itm": r.in_the_money,
        }
        for key in ("top", "place", "show", "itm"):
            if stored_flags[key] == derived[key]:
                stored_match_rederived[key] += 1
            else:
                stored_disagreement.append({
                    "race_id": r.race_id,
                    "key": key,
                    "stored": stored_flags[key],
                    "rederived": derived[key],
                })

    # Cross-check N most-recent rows against the live racing API.
    # If our stored actual_first matches what the API says now, our
    # data fetch and persistence are correct.
    SAMPLE_SIZE = 10
    live_check = []
    for r in rows[:SAMPLE_SIZE]:
        try:
            if "-" in r.race_id:
                meet_id, race_number = r.race_id.rsplit("-", 1)
                from app.services import racing_api
                meet_results = await racing_api.get_na_meet_results(meet_id)
                api_actual_first = api_actual_second = api_actual_third = None
                for race in meet_results.get("races", []):
                    rk = race.get("race_key") or {}
                    rnum = str(rk.get("race_number", "")) if isinstance(rk, dict) else ""
                    if rnum == str(race_number):
                        for runner in race.get("runners", []):
                            pos = (
                                runner.get("official_finish_position")
                                or runner.get("finish_position")
                                or runner.get("position")
                            )
                            try: pos = int(str(pos).strip())
                            except (ValueError, TypeError): continue
                            name = runner.get("horse") or runner.get("horse_name") or ""
                            if pos == 1: api_actual_first = name
                            elif pos == 2: api_actual_second = name
                            elif pos == 3: api_actual_third = name
                        break
                live_check.append({
                    "race_id": r.race_id,
                    "race_date": str(r.race_date) if r.race_date else None,
                    "stored": {
                        "actual_first": r.actual_first,
                        "actual_second": r.actual_second,
                        "actual_third": r.actual_third,
                    },
                    "live_api": {
                        "actual_first": api_actual_first,
                        "actual_second": api_actual_second,
                        "actual_third": api_actual_third,
                    },
                    "match_first":  _norm(r.actual_first)  == _norm(api_actual_first),
                    "match_second": _norm(r.actual_second) == _norm(api_actual_second),
                    "match_third":  _norm(r.actual_third)  == _norm(api_actual_third),
                })
        except Exception as e:
            live_check.append({"race_id": r.race_id, "error": str(e)})

    return JSONResponse({
        "total_rows": len(rows),
        "stored_vs_rederived_matches": stored_match_rederived,  # out of total_rows
        "stored_vs_rederived_disagreements": stored_disagreement[:20],
        "live_api_cross_check": live_check,
        "live_api_summary": {
            "checked": sum(1 for x in live_check if "error" not in x),
            "first_matches": sum(1 for x in live_check if x.get("match_first")),
            "second_matches": sum(1 for x in live_check if x.get("match_second")),
            "third_matches": sum(1 for x in live_check if x.get("match_third")),
            "errors": sum(1 for x in live_check if "error" in x),
        },
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
