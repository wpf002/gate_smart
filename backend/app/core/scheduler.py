"""
Nightly job scheduler — runs automatically when the FastAPI server starts.

Schedule (all UTC, summer EDT = UTC-4):
  15:00  nightly_predict_all.py    — 11:00 AM ET, pre-race haiku predictions
  15:30  morning_line_email.py     — 11:30 AM ET, Secretariat's Morning Line email
  10:00  nightly_accuracy.py       — 6:00 AM ET next morning, settle + email digest
  03:30  nightly_recalibration.py  — 11:30 PM ET, recalibrate prompt weights
  04:00  nightly_reflect.py        — midnight ET, Secretariat reflection layer
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
    await _run_script("nightly_predict_all.py")


async def job_morning_line() -> None:
    await _run_script("morning_line_email.py")


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


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(job_predict_all,  CronTrigger(hour=15, minute=0),  id="predict_all",  name="Morning predictions (11 AM ET)")
    scheduler.add_job(job_morning_line, CronTrigger(hour=15, minute=30), id="morning_line", name="Secretariat's Morning Line email (11:30 AM ET)")
    scheduler.add_job(job_accuracy,     CronTrigger(hour=10, minute=0),  id="accuracy",     name="Morning accuracy + email (6 AM ET)")
    scheduler.add_job(job_recalibration,CronTrigger(hour=3,  minute=30), id="recalibration",name="Prompt recalibration (11:30 PM ET)")
    scheduler.add_job(job_reflect,      CronTrigger(hour=4,  minute=0),  id="reflect",      name="Secretariat reflection (midnight ET)")
    scheduler.add_job(job_race_alerts,  IntervalTrigger(minutes=5),      id="race_alerts",  name="Race alerts (every 5 min)")

    return scheduler
