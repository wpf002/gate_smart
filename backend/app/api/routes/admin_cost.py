"""
Admin: Anthropic API cost dashboard.

Reads `llm_call_log` (populated by app.core.llm_cost.tracked_create) and returns
daily totals and per-endpoint breakdown. Gated to the project owner's email.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.accuracy import LLMCallLog
from app.models.user import User

router = APIRouter()


def _admin_emails() -> set[str]:
    raw = (settings.DAILY_REPORT_EMAIL or "").lower()
    return {e.strip() for e in raw.split(",") if e.strip()}


def _require_admin(user: User) -> None:
    if (user.email or "").lower() not in _admin_emails():
        raise HTTPException(status_code=403, detail="Admin only")


@router.get("/summary")
async def cost_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Per-day total cost over the last `days` days."""
    _require_admin(user)
    days = max(1, min(days, 90))
    since = datetime.date.today() - datetime.timedelta(days=days - 1)

    result = await db.execute(
        select(
            LLMCallLog.call_date,
            func.count(LLMCallLog.id).label("calls"),
            func.sum(LLMCallLog.input_tokens).label("input_tokens"),
            func.sum(LLMCallLog.output_tokens).label("output_tokens"),
            func.sum(LLMCallLog.web_searches).label("web_searches"),
            func.sum(LLMCallLog.est_cost_usd).label("cost_usd"),
        )
        .where(LLMCallLog.call_date >= since)
        .group_by(LLMCallLog.call_date)
        .order_by(desc(LLMCallLog.call_date))
    )

    rows = [
        {
            "date": r.call_date.isoformat(),
            "calls": int(r.calls or 0),
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "web_searches": int(r.web_searches or 0),
            "cost_usd": round(float(r.cost_usd or 0.0), 4),
        }
        for r in result.all()
    ]
    total_cost = round(sum(r["cost_usd"] for r in rows), 4)
    return {"days": days, "total_cost_usd": total_cost, "by_date": rows}


@router.get("/by_user")
async def cost_by_user(
    days: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cost broken down by user over the last `days` days, sorted highest first.

    Rows with user_id IS NULL are background/system calls (nightly_predict_all,
    nightly_reflect, daily email) — returned as a single 'system' row so they
    don't dominate the per-user breakdown.
    """
    _require_admin(user)
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 500))
    since = datetime.date.today() - datetime.timedelta(days=days - 1)

    result = await db.execute(
        select(
            LLMCallLog.user_id,
            func.count(LLMCallLog.id).label("calls"),
            func.sum(LLMCallLog.input_tokens).label("input_tokens"),
            func.sum(LLMCallLog.output_tokens).label("output_tokens"),
            func.sum(LLMCallLog.est_cost_usd).label("cost_usd"),
        )
        .where(LLMCallLog.call_date >= since)
        .group_by(LLMCallLog.user_id)
        .order_by(desc("cost_usd"))
        .limit(limit)
    )
    raw = result.all()

    # Resolve user_ids to emails in a single query (skip the NULL bucket).
    user_ids = [r.user_id for r in raw if r.user_id is not None]
    email_by_id: dict[int, str] = {}
    if user_ids:
        emails = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
        email_by_id = {row.id: row.email for row in emails.all()}

    rows = [
        {
            "user_id": r.user_id,
            "email": email_by_id.get(r.user_id) if r.user_id is not None else "system",
            "calls": int(r.calls or 0),
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "cost_usd": round(float(r.cost_usd or 0.0), 4),
        }
        for r in raw
    ]
    return {
        "since": since.isoformat(),
        "until": datetime.date.today().isoformat(),
        "days": days,
        "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "by_user": rows,
    }


@router.get("/by_endpoint")
async def cost_by_endpoint(
    date: str | None = None,
    days: int = 1,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cost broken down by endpoint + model for a single day (default: today),
    or aggregated across the last `days` days if `date` is omitted."""
    _require_admin(user)

    if date:
        try:
            target = datetime.date.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format — use YYYY-MM-DD")
        since = until = target
    else:
        days = max(1, min(days, 90))
        until = datetime.date.today()
        since = until - datetime.timedelta(days=days - 1)

    result = await db.execute(
        select(
            LLMCallLog.endpoint,
            LLMCallLog.model,
            func.count(LLMCallLog.id).label("calls"),
            func.sum(LLMCallLog.input_tokens).label("input_tokens"),
            func.sum(LLMCallLog.output_tokens).label("output_tokens"),
            func.sum(LLMCallLog.web_searches).label("web_searches"),
            func.sum(LLMCallLog.est_cost_usd).label("cost_usd"),
        )
        .where(LLMCallLog.call_date >= since)
        .where(LLMCallLog.call_date <= until)
        .group_by(LLMCallLog.endpoint, LLMCallLog.model)
        .order_by(desc("cost_usd"))
    )

    rows = [
        {
            "endpoint": r.endpoint,
            "model": r.model,
            "calls": int(r.calls or 0),
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "web_searches": int(r.web_searches or 0),
            "cost_usd": round(float(r.cost_usd or 0.0), 4),
            "avg_cost_per_call_usd": round(float(r.cost_usd or 0.0) / max(int(r.calls or 1), 1), 4),
        }
        for r in result.all()
    ]
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "by_endpoint": rows,
    }
