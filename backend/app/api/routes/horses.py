from fastapi import APIRouter

router = APIRouter()


@router.get("/{horse_id}")
async def horse_profile(horse_id: str):
    return {"horse_id": horse_id}


@router.get("/{horse_id}/results")
async def horse_results(horse_id: str):
    return {"horse_id": horse_id, "results": []}


@router.get("/{horse_id}/explain")
async def horse_explain(horse_id: str):
    return {"horse_id": horse_id, "explanation": ""}


@router.get("/{horse_id}/form/decode")
async def horse_form_decode(horse_id: str, form: str = ""):
    return {"horse_id": horse_id, "form": form, "decoded": []}
