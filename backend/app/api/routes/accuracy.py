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
            "message": "Today's report generates tomorrow morning at 6 AM ET",
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


@router.post("/resettle")
async def resettle_date(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Re-fetch race results and re-settle predictions for a given date.
    Resets result_fetched=False, then re-runs the settlement logic.
    Protected by admin_key matching SECRET_KEY.
    """
    import datetime as dt
    import sqlalchemy

    if payload.get("admin_key") != settings.SECRET_KEY:
        raise HTTPException(status_code=403, detail="Not authorised")

    date_str = payload.get("date")
    try:
        target = dt.date.fromisoformat(date_str) if date_str else dt.date.today() - dt.timedelta(days=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format — use YYYY-MM-DD")

    # Ensure new columns exist
    from app.core.database import _engine
    ddl = [
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS reflection TEXT",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS region VARCHAR(10)",
        "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS lessons JSONB",
    ]
    async with _engine.begin() as conn:
        for stmt in ddl:
            await conn.execute(sqlalchemy.text(stmt))

    from app.models.accuracy import RacePrediction, DailyAccuracyReport
    from sqlalchemy import update

    # 1. Reset predictions to unsettled
    await db.execute(
        update(RacePrediction)
        .where(RacePrediction.race_date == target)
        .values(
            result_fetched=False,
            actual_first=None,
            actual_second=None,
            actual_third=None,
            top_pick_correct=False,
            in_the_money=False,
            settled_at=None,
        )
    )
    await db.commit()

    # 2. Fetch results from both APIs
    from app.services.racing_api import get_na_results_full, get_results
    date_iso = target.isoformat()

    try:
        na_data = await get_na_results_full(date_iso)
        na_by_id = {r.get("race_id"): r for r in na_data.get("results", []) if r.get("race_id")}
    except Exception:
        na_by_id = {}

    try:
        int_data = await get_results(date=date_iso)
        int_by_id = {r.get("race_id"): r for r in int_data.get("results", []) if r.get("race_id")}
    except Exception:
        int_by_id = {}

    all_by_id = {**int_by_id, **na_by_id}

    # 3. Load unsettled predictions
    preds_res = await db.execute(
        select(RacePrediction).where(
            RacePrediction.race_date == target,
            RacePrediction.result_fetched == False,  # noqa: E712
        )
    )
    predictions = preds_res.scalars().all()

    def _norm(name: str) -> str:
        return (name or "").lower().strip().replace("'", "").replace("-", " ")

    def _finisher(runners: list, pos: int):
        for r in runners:
            p = r.get("position") or r.get("finish_position") or r.get("place")
            try:
                if int(str(p).strip()) == pos:
                    return r.get("horse") or r.get("horse_name", "") or None
            except (ValueError, TypeError):
                pass
        return None

    settled = []
    now = dt.datetime.now(dt.timezone.utc)
    for pred in predictions:
        race_result = all_by_id.get(pred.race_id)
        if not race_result:
            continue
        runners = race_result.get("runners", [])
        actual_first = _finisher(runners, 1)
        actual_second = _finisher(runners, 2)
        actual_third = _finisher(runners, 3)
        top_correct = bool(
            actual_first and pred.predicted_first and
            _norm(actual_first) == _norm(pred.predicted_first)
        )
        itm = bool(
            pred.predicted_first and (
                _norm(pred.predicted_first) == _norm(actual_first or "") or
                _norm(pred.predicted_first) == _norm(actual_second or "") or
                _norm(pred.predicted_first) == _norm(actual_third or "")
            )
        )
        await db.execute(
            update(RacePrediction)
            .where(RacePrediction.id == pred.id)
            .values(
                actual_first=actual_first,
                actual_second=actual_second,
                actual_third=actual_third,
                result_fetched=True,
                top_pick_correct=top_correct,
                in_the_money=itm,
                settled_at=now,
            )
        )
        settled.append({"top_correct": top_correct, "itm": itm})

    await db.commit()

    # 4. Update DailyAccuracyReport
    total = len(settled)
    wins = sum(1 for s in settled if s["top_correct"])
    itm_count = sum(1 for s in settled if s["itm"])
    win_rate = wins / total if total else 0.0
    itm_rate = itm_count / total if total else 0.0

    from sqlalchemy.dialects.postgresql import insert as pg_insert
    report_row = {
        "report_date": target,
        "total_races": total,
        "races_analyzed": total,
        "top_pick_wins": wins,
        "in_the_money": itm_count,
        "win_rate": win_rate,
        "itm_rate": itm_rate,
    }
    stmt = pg_insert(DailyAccuracyReport).values(**report_row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["report_date"],
        set_={k: v for k, v in report_row.items() if k != "report_date"},
    )
    await db.execute(stmt)
    await db.commit()

    # 5. Re-send corrected email
    preds_res2 = await db.execute(
        select(RacePrediction).where(
            RacePrediction.race_date == target,
            RacePrediction.result_fetched == True,  # noqa: E712
        )
    )
    preds_list = preds_res2.scalars().all()

    report_res = await db.execute(
        select(DailyAccuracyReport).where(DailyAccuracyReport.report_date == target)
    )
    report_obj = report_res.scalar_one()

    from app.services.secretariat import generate_daily_email_report
    from app.services.email_service import send_daily_report

    email_content = await generate_daily_email_report(report_obj, preds_list)
    sent = await send_daily_report(
        subject=email_content.get("subject", f"Secretariat [Corrected] — {target.isoformat()}"),
        html_body=email_content.get("html", ""),
        text_body=email_content.get("text", ""),
    )

    return {
        "date": target.isoformat(),
        "results_found": len(all_by_id),
        "predictions_reset": len(predictions),
        "settled": total,
        "wins": wins,
        "win_rate": win_rate,
        "email_sent": sent,
    }


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
    admin_key = payload.get("admin_key")
    if not (admin_key and admin_key == settings.SECRET_KEY) and (not user or user.email != settings.DAILY_REPORT_EMAIL):
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
