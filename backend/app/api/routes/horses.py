from fastapi import APIRouter, HTTPException

from app.services import racing_api, secretariat

router = APIRouter()


@router.get("/search")
async def horse_search(name: str = ""):
    try:
        return await racing_api.search_horses(name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/{horse_id}")
async def horse_profile(horse_id: str):
    try:
        return await racing_api.get_horse(horse_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/{horse_id}/results")
async def horse_results(horse_id: str, limit: int = 10):
    try:
        return await racing_api.get_horse_results(horse_id, limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Racing API error: {exc}") from exc


@router.get("/{horse_id}/explain")
async def horse_explain(horse_id: str):
    try:
        horse_data = await racing_api.get_horse(horse_id)
        results = await racing_api.get_horse_results(horse_id)
        horse_data["recent_results"] = results
        explanation = await secretariat.explain_horse(horse_data)
        return {"horse_id": horse_id, "analysis": explanation}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error: {exc}") from exc


@router.get("/{horse_id}/form/decode")
async def horse_form_decode(horse_id: str, form: str = ""):
    try:
        horse_data = await racing_api.get_horse(horse_id)
        horse_name = horse_data.get("horse", horse_id)
        result = await secretariat.explain_form_string(form, horse_name)
        return {"horse_id": horse_id, "form": form, "decoded": result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error: {exc}") from exc
