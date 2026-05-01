from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.equibase import HorsePastPerformance
from app.services import racing_api, secretariat
from app.services.equibase_api import make_horse_name_key

router = APIRouter()


async def _find_runner_in_racecards(horse_id: str) -> tuple[dict | None, dict | None]:
    """Search today's and tomorrow's racecards for a runner by horse_id (UK/IRE + NA)."""
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

    # Also search NA racecards
    for day in (None, "tomorrow"):
        try:
            data = await racing_api.get_na_racecards_full(date=day)
            for race in data.get("racecards", []):
                for runner in race.get("runners", []):
                    if runner.get("horse_id") == horse_id:
                        race_ctx = {k: v for k, v in race.items() if k != "runners"}
                        return runner, race_ctx
        except Exception:
            continue

    return None, None


def _dedupe_horses(horses: list) -> list:
    """Collapse duplicate entries for the same horse.

    The Racing API search can return the same horse multiple times when the
    name appears across feeds (form database, current entries, etc.) often
    with subtly different trainer spellings. Dedupe on (name + course); keep
    the entry with more populated fields and merge in any missing values
    from the discarded entry.
    """
    def _filled_count(h: dict) -> int:
        return sum(1 for v in h.values() if v not in (None, "", [], {}))

    by_key: dict[tuple[str, str], dict] = {}
    for h in horses:
        name = (h.get("horse_name") or h.get("horse") or "").strip().lower()
        course = (h.get("course") or "").strip().lower()
        key = (name, course)
        if not name:
            by_key[(id(h), "")] = h
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = h
            continue
        keep, drop = (h, existing) if _filled_count(h) > _filled_count(existing) else (existing, h)
        merged = {**drop, **{k: v for k, v in keep.items() if v not in (None, "", [], {})}}
        by_key[key] = merged
    return list(by_key.values())


@router.get("/search")
async def horse_search(q: str = ""):
    """Search by name — API first, local racecard fallback."""
    if not q or len(q.strip()) < 2:
        return {"horses": [], "total": 0}

    q_stripped = q.strip()

    # Try the Racing API search endpoint (Standard plan)
    try:
        api_result = await racing_api.search_horses(q_stripped)
        horses = _dedupe_horses(api_result.get("horses", []))
        if horses:
            return {"horses": horses, "total": len(horses), "source": "api"}
    except Exception:
        pass

    # Fallback: search through locally cached racecard runners (UK/IRE + NA)
    q_lower = q_stripped.lower()
    horses = []
    seen_ids: set[str] = set()

    def _collect_runners(racecards: list) -> None:
        for race in racecards:
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

    # UK/IRE racecards
    for day in (None, "tomorrow"):
        try:
            data = await racing_api.get_racecards(date=day)
            _collect_runners(data.get("racecards", []))
        except Exception:
            continue

    # NA racecards (today + tomorrow)
    for day in (None, "tomorrow"):
        try:
            data = await racing_api.get_na_racecards_full(date=day)
            _collect_runners(data.get("racecards", []))
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


@router.get("/{horse_id}/past-performances")
async def horse_past_performances(
    horse_id: str,
    name: str = Query(default=None, description="Horse name override for Equibase lookup"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return Equibase past performance records for a horse from Postgres.
    horse_id is used to find the horse name from today's racecards; pass ?name= to override.
    """
    horse_name = name
    if not horse_name:
        runner, _ = await _find_runner_in_racecards(horse_id)
        if runner:
            horse_name = runner.get("horse_name") or runner.get("horse", "")
        else:
            horse_name = horse_id

    eq_key = make_horse_name_key(horse_name)
    result = await db.execute(
        select(HorsePastPerformance)
        .where(HorsePastPerformance.horse_name_key == eq_key)
        .order_by(HorsePastPerformance.pp_race_date.desc())
        .limit(30)
    )
    rows = result.scalars().all()

    pp_list = [
        {c.name: getattr(row, c.name) for c in HorsePastPerformance.__table__.columns if c.name != "id"}
        for row in rows
    ]
    return {"horse_id": horse_id, "horse_name": horse_name, "past_performances": pp_list, "total": len(pp_list)}


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
