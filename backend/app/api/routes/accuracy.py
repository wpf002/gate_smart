"""
Accuracy API — daily report retrieval, history, and manual email trigger.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user
from app.core.config import settings
from app.core.database import get_db
from app.models.accuracy import DailyAccuracyReport
from app.models.user import User

router = APIRouter()


@router.get("/daily")
async def get_daily_accuracy(
    date: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Return DailyAccuracyReport for a given date (defaults to today)."""
    if date:
        try:
            target = datetime.date.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format — use YYYY-MM-DD")
    else:
        target = datetime.date.today()

    result = await db.execute(
        select(DailyAccuracyReport).where(DailyAccuracyReport.report_date == target)
    )
    report = result.scalar_one_or_none()

    if not report:
        return {
            "status": "pending",
            "message": "Today's report generates tonight at 11 PM ET",
            "date": target.isoformat(),
        }

    return {
        "status": "ok",
        "date": report.report_date.isoformat(),
        "total_races": report.total_races,
        "races_analyzed": report.races_analyzed,
        "top_pick_wins": report.top_pick_wins,
        "in_the_money": report.in_the_money,
        "win_rate": report.win_rate,
        "itm_rate": report.itm_rate,
        "best_call": report.best_call,
        "worst_miss": report.worst_miss,
        "by_mode": report.by_mode,
        "by_track": report.by_track,
        "by_race_type": report.by_race_type,
        "email_sent": report.email_sent,
        "email_sent_at": report.email_sent_at.isoformat() if report.email_sent_at else None,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/history")
async def get_accuracy_history(db: AsyncSession = Depends(get_db)):
    """Return the last 30 days of DailyAccuracyReports, newest first."""
    result = await db.execute(
        select(DailyAccuracyReport)
        .order_by(desc(DailyAccuracyReport.report_date))
        .limit(30)
    )
    reports = result.scalars().all()

    return [
        {
            "date": r.report_date.isoformat(),
            "races_analyzed": r.races_analyzed,
            "top_pick_wins": r.top_pick_wins,
            "win_rate": r.win_rate,
            "itm_rate": r.itm_rate,
            "best_call": r.best_call,
        }
        for r in reports
    ]


@router.post("/send-report")
async def trigger_send_report(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_optional_user),
):
    """
    Manually trigger email send for a given date.
    Requires the requesting user's email to match DAILY_REPORT_EMAIL.
    """
    if not user or user.email != settings.DAILY_REPORT_EMAIL:
        raise HTTPException(status_code=403, detail="Not authorised")

    date_str = payload.get("date")
    try:
        target = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format — use YYYY-MM-DD")

    result = await db.execute(
        select(DailyAccuracyReport).where(DailyAccuracyReport.report_date == target)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for {target.isoformat()}")

    from app.models.accuracy import RacePrediction
    preds_result = await db.execute(
        select(RacePrediction).where(
            RacePrediction.race_date == target,
            RacePrediction.result_fetched == True,  # noqa: E712
        )
    )
    predictions = preds_result.scalars().all()

    from app.services.secretariat import generate_daily_email_report
    from app.services.email_service import send_daily_report

    email_content = await generate_daily_email_report(report, predictions)
    sent = await send_daily_report(
        subject=email_content.get("subject", f"Secretariat Daily Report — {target.isoformat()}"),
        html_body=email_content.get("html", ""),
        text_body=email_content.get("text", ""),
    )

    if sent:
        import datetime as dt
        report.email_sent = True
        report.email_sent_at = dt.datetime.now(dt.timezone.utc)
        await db.commit()

    return {"sent": sent, "date": target.isoformat()}
