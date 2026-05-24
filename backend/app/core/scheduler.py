"""
Nightly job scheduler — runs automatically when the FastAPI server starts.

Schedule (all UTC, summer EDT = UTC-4):
  12:00  nightly_predict_all.py    — 8:00 AM ET, pre-race full analysis
  15:35  substack_draft_email.py   — 11:35 AM ET, Substack-ready draft email
  10:00  nightly_accuracy.py       — 6:00 AM ET next morning, settle + email digest
  03:30  nightly_recalibration.py  — 11:30 PM ET, recalibrate prompt weights
  04:00  nightly_reflect.py        — midnight ET, Secretariat reflection layer

predict_all is intentionally early: race-day users open the app well before
afternoon cards. The prior 11 AM ET slot left morning users seeing "morning
line unavailable" on every race for hours.
"""
import asyncio
import datetime
import logging
import os
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)

# Path to the scripts directory
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts")


async def _run_script(script_name: str, extra_args: list[str] | None = None) -> None:
    """Run a nightly script as a subprocess, streaming its output to logs."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + (extra_args or [])
    print(f"[scheduler] Starting {script_name}", flush=True)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace").strip()
        if output:
            for line in output.splitlines():
                print(f"[{script_name}] {line}", flush=True)
        if proc.returncode == 0:
            print(f"[scheduler] {script_name} completed successfully", flush=True)
        else:
            print(f"[scheduler] {script_name} FAILED with exit code {proc.returncode}", flush=True)
    except Exception as e:
        print(f"[scheduler] {script_name} raised an exception: {e}", flush=True)
        log.exception(f"[scheduler] {script_name} raised an exception: {e}")


async def job_predict_all() -> None:
    global _predict_all_last_attempt
    _predict_all_last_attempt = datetime.datetime.now(datetime.timezone.utc)
    await _run_script("nightly_predict_all.py")


async def job_substack_draft() -> None:
    await _run_script("substack_draft_email.py")


async def job_accuracy() -> None:
    await _run_script("nightly_accuracy.py")


async def job_recalibration() -> None:
    await _run_script("nightly_recalibration.py")


async def job_reflect() -> None:
    await _run_script("nightly_reflect.py")


async def job_race_alerts() -> None:
    try:
        from app.services.race_alerts import check_and_send_race_alerts
        await check_and_send_race_alerts()
    except Exception as e:
        log.warning(f"[scheduler] race_alerts failed: {e}")


async def job_smoke_check() -> None:
    try:
        from app.services.smoke_check import run_smoke_check
        await run_smoke_check()
    except Exception as e:
        log.warning(f"[scheduler] smoke_check failed: {e}")


# Catchup threshold: a real run writes a row per race (~140–170/day on weekends,
# ~30–60 on weekdays). Anything under 10 by mid-morning is "almost certainly
# missed" — the only days with under 10 NA races are major US holidays, and
# re-firing on those is harmless (idempotent via on_conflict_do_nothing).
_PREDICT_ALL_HEALTHY_THRESHOLD = 10

# Cooldown between predict_all launches. A full run takes ~15 min; if it fails
# (e.g., Haiku rate-limited) and writes < threshold rows, the every-15-min
# catchup would otherwise re-fire it immediately, compounding the rate-limit
# pressure. 60 min lets a real run finish and write rows (so the count check
# bails), while still allowing ~5 retry windows per 8-hour catchup band for
# genuinely catastrophic failures. In-memory state resets on container restart,
# which is desirable — a restart is itself one of the failure modes catchup
# exists to heal, so we WANT the next catchup to fire after a deploy.
_PREDICT_ALL_COOLDOWN_MIN = 60
_predict_all_last_attempt: datetime.datetime | None = None


async def job_predict_all_catchup() -> None:
    """Self-healing predict-all check. Runs every 15 min between 8 AM and 4 PM ET.

    Fires nightly_predict_all if today has fewer than _PREDICT_ALL_HEALTHY_THRESHOLD
    auto_daily rows AND no predict_all attempt has fired in the last
    _PREDICT_ALL_COOLDOWN_MIN minutes. Heals three failure modes the cron
    alone cannot:
      1. Container started AFTER the scheduled fire (deploy at 9 AM, cron at 8 AM)
      2. Crash mid-run leaving partial rows
      3. APScheduler in-process job silently dropped (rare but observed)

    Idempotent: predict-all writes use on_conflict_do_nothing. max_instances=1
    on this job prevents two catchups racing each other. The cooldown stops the
    catchup from re-firing predict_all on top of an in-flight or recently-failed
    run — without it, a Haiku-throttled run that writes < threshold rows would
    be relaunched every 15 minutes, compounding the rate-limit pressure.
    """
    global _predict_all_last_attempt
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import func, select

    from app.core import database as _db
    from app.models.accuracy import RacePrediction

    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)
    if now_et.hour < 8 or now_et.hour >= 16:
        return

    if _predict_all_last_attempt is not None:
        age_min = (datetime.now(timezone.utc) - _predict_all_last_attempt).total_seconds() / 60
        if age_min < _PREDICT_ALL_COOLDOWN_MIN:
            return

    today = now_et.date()
    try:
        async with _db._AsyncSessionLocal() as db:
            result = await db.execute(
                select(func.count(RacePrediction.id)).where(
                    RacePrediction.race_date == today,
                    RacePrediction.analysis_mode == "auto_daily",
                    RacePrediction.user_id.is_(None),
                )
            )
            count = int(result.scalar_one() or 0)
    except Exception as e:
        log.warning(f"[scheduler] catchup db check failed: {e}")
        return

    if count >= _PREDICT_ALL_HEALTHY_THRESHOLD:
        return

    print(f"[scheduler] catchup: only {count} predictions for {today.isoformat()} — firing predict_all", flush=True)
    _predict_all_last_attempt = datetime.now(timezone.utc)
    await _run_script("nightly_predict_all.py")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Catchup fires 30s after startup (so deploys self-heal immediately) and
    # then every 15 min. The job itself bails outside the 8 AM–4 PM ET window.
    catchup_first_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=30)

    scheduler.add_job(job_predict_all,  CronTrigger(hour=12, minute=0),  id="predict_all",  name="Morning predictions (8 AM ET)")
    scheduler.add_job(job_predict_all_catchup, IntervalTrigger(minutes=15, start_date=catchup_first_run), id="predict_all_catchup", name="Predict-all self-heal (every 15 min, 8 AM–4 PM ET)", max_instances=1, coalesce=True)
    scheduler.add_job(job_substack_draft, CronTrigger(hour=15, minute=35), id="substack_draft", name="Substack draft email (11:35 AM ET)")
    scheduler.add_job(job_accuracy,     CronTrigger(hour=10, minute=0),  id="accuracy",     name="Morning accuracy + email (6 AM ET)")
    scheduler.add_job(job_recalibration,CronTrigger(hour=3,  minute=30), id="recalibration",name="Prompt recalibration (11:30 PM ET)")
    scheduler.add_job(job_reflect,      CronTrigger(hour=4,  minute=0),  id="reflect",      name="Secretariat reflection (midnight ET)")
    scheduler.add_job(job_race_alerts,  IntervalTrigger(minutes=5),      id="race_alerts",  name="Race alerts (every 5 min)")
    scheduler.add_job(job_smoke_check,  IntervalTrigger(minutes=5),      id="smoke_check",  name="Prod smoke check (every 5 min)")

    return scheduler
