"""
Nightly job scheduler — runs automatically when the FastAPI server starts.

Schedule (all UTC, summer EDT = UTC-4):
  12:00  nightly_predict_all.py    — 8:00 AM ET, pre-race haiku predictions
  03:00  nightly_accuracy.py       — 11:00 PM ET, settle results + email digest
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

log = logging.getLogger(__name__)

# Path to the scripts directory
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts")


async def _run_script(script_name: str, extra_args: list[str] | None = None) -> None:
    """Run a nightly script as a subprocess, streaming its output to logs."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + (extra_args or [])
    log.info(f"[scheduler] Starting {script_name}")
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
                log.info(f"[{script_name}] {line}")
        if proc.returncode == 0:
            log.info(f"[scheduler] {script_name} completed successfully")
        else:
            log.error(f"[scheduler] {script_name} exited with code {proc.returncode}")
    except Exception as e:
        log.exception(f"[scheduler] {script_name} raised an exception: {e}")


async def job_predict_all() -> None:
    await _run_script("nightly_predict_all.py")


async def job_accuracy() -> None:
    await _run_script("nightly_accuracy.py")


async def job_recalibration() -> None:
    await _run_script("nightly_recalibration.py")


async def job_reflect() -> None:
    await _run_script("nightly_reflect.py")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(job_predict_all,  CronTrigger(hour=12, minute=0),  id="predict_all",  name="Morning predictions (8 AM ET)")
    scheduler.add_job(job_accuracy,     CronTrigger(hour=3,  minute=0),  id="accuracy",     name="Nightly accuracy + email (11 PM ET)")
    scheduler.add_job(job_recalibration,CronTrigger(hour=3,  minute=30), id="recalibration",name="Prompt recalibration (11:30 PM ET)")
    scheduler.add_job(job_reflect,      CronTrigger(hour=4,  minute=0),  id="reflect",      name="Secretariat reflection (midnight ET)")

    return scheduler
