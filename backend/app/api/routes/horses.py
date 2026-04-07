from fastapi import APIRouter, HTTPException

from app.services import racing_api, secretariat

router = APIRouter()


async def _find_runner_in_racecards(horse_id: str) -> tuple[dict | None, dict | None]:
    """Search today's and tomorrow's racecards for a runner by horse_id."""
    for day in (None, "tomorrow"):
        try:
            data = await racing_api.get_racecards(date=day)
            for race in data.get("racecards", []):
                for runner in race.get("runners", []):
                    if runner.get("horse_id") == horse_id:
                        race_ctx = {k: v for k, v in race.items() if k != "runners"}
                        return runner, race_ctx
        except Exception:
            continue
    return None, None


@router.get("/search")
async def horse_search(q: str = ""):
    """Search by name — API first, local racecard fallback."""
    if not q or len(q.strip()) < 2:
        return {"horses": [], "total": 0}

    q_stripped = q.strip()

    # Try the Racing API search endpoint (Standard plan)
    try:
        api_result = await racing_api.search_horses(q_stripped)
        horses = api_result.get("horses", [])
        if horses:
            return {"horses": horses, "total": len(horses), "source": "api"}
    except Exception:
        pass

    # Fallback: search through locally cached racecard runners
    q_lower = q_stripped.lower()
    horses = []
    seen_ids: set[str] = set()

    for day in (None, "tomorrow"):
        try:
            data = await racing_api.get_racecards(date=day)
            for race in data.get("racecards", []):
                for runner in race.get("runners", []):
                    horse_name = runner.get("horse_name") or runner.get("horse", "")
                    if q_lower in horse_name.lower():
                        hid = runner.get("horse_id", horse_name)
                        if hid not in seen_ids:
                            seen_ids.add(hid)
                            horses.append({
                                **runner,
                                "race_id": race.get("race_id"),
                                "race_name": race.get("title") or race.get("race_name"),
                                "course": race.get("course"),
                                "off_time": race.get("time") or race.get("off_time"),
                            })
        except Exception:
            continue

    return {"horses": horses, "total": len(horses), "source": "local"}


@router.get("/{horse_id}")
async def horse_profile(horse_id: str):
    """Horse data from racecard runners (Standard plan has no standalone profile endpoint)."""
    runner, race_ctx = await _find_runner_in_racecards(horse_id)
    if runner:
        return {**runner, **({"race_context": race_ctx} if race_ctx else {})}
    raise HTTPException(status_code=404, detail="Horse not found in today's or tomorrow's races")


@router.get("/{horse_id}/explain")
async def horse_explain(horse_id: str):
    runner, race_ctx = await _find_runner_in_racecards(horse_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Horse not found")
    try:
        explanation = await secretariat.explain_horse(runner, race_ctx)
        return {"horse_id": horse_id, "analysis": explanation}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI analysis unavailable")


@router.get("/{horse_id}/form/decode")
async def horse_form_decode(horse_id: str, form: str = ""):
    runner, _ = await _find_runner_in_racecards(horse_id)
    horse_name = runner.get("horse_name") or horse_id if runner else horse_id
    if not form and runner:
        form = runner.get("form", "")
    if not form:
        raise HTTPException(status_code=400, detail="No form string available")
    try:
        result = await secretariat.explain_form_string(form, horse_name)
        return {"horse_id": horse_id, "form": form, "decoded": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI analysis unavailable")
