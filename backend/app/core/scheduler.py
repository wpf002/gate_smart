"""
In-process scheduler — runs automatically when the FastAPI server starts.

Owns ALL nightly work for GateSmart. The Railway cron services
(predict-daily, reflect-nightly, recalibrate-nightly, accuracy-nightly) are
no longer used: they never actually executed their scripts because
railway.toml's file-level startCommand overrode their per-service overrides,
so the cron containers booted uvicorn instead of running the intended script.
The work was silently being done by THIS scheduler all along. When commit
f3018ad removed the nightly triggers expecting the cron services to take
over, accuracy + reflect + recalibrate stopped happening entirely.

Now everything runs from here, against the backend container that has the
env vars. The cron services should be deleted (they don't fire anything).

Schedule (UTC):
  03:30  nightly_recalibration.py  — 30-day rolling recalibration
  10:00  nightly_accuracy.py       — settle yesterday's races + email digest
  12:00  predict_all (via 8 AM ET catchup, see below)
  15:00  predict_all --only-missing — second pass, fills tracks the 8 AM run
                                       missed (late-posting cards / feed blips)
  14:30  nightly_reflect.py        — reflect on settled races + synth lessons
                                      (MUST run after accuracy settles — the
                                       old 04:00 slot ran before the data existed)

Continuous:
  every 30m  accuracy_catchup        — self-heal accuracy 10:00–14:00 UTC
  every 15m  predict_all_catchup     — self-heal predict_all 08:00–16:00 ET
  every 5m   race_alerts, smoke_check — race-time + uptime

Double-fire guard:
  RAILWAY_SERVICE_NAME must be "backend" (or unset for local dev) for the
  scheduler to register. If a cron container ever boots start.sh, it bails
  here instead of spinning up a competing scheduler against the same DB.

Idempotency (so a restart-triggered re-fire is safe):
  accuracy   — script filters result_fetched=False; report row uses
               on_conflict_do_update; email_sent flag prevents re-emailing
               an already-sent report (see catchup logic below).
  reflect    — script filters reflection IS NULL (added 2026-05-27).
  recalibrate — overwrites the single calibration row; cost-bounded.
  predict_all — RacePrediction inserts use on_conflict_do_nothing.

misfire_grace_time=3600 on the nightly triggers means a backend that
restarts within an hour of the scheduled time still fires the job —
covers the deploy-during-cron-window case.
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


async def job_watchlist_alerts() -> None:
    """Notify users when a followed horse/trainer/jockey is entered today.
    Deduped per (user, entity, race), so running it twice is safe."""
    try:
        from app.services.watchlist_alerts import check_watchlist_alerts
        await check_watchlist_alerts()
    except Exception as e:
        log.exception(f"[scheduler] watchlist_alerts raised: {e}")


async def job_predict_all_second_pass() -> None:
    """Second predict pass at 11 AM ET, filling tracks the 8 AM run missed —
    late-posting cards, or a transient feed blip like 2026-07-21 where only 2
    tracks were captured and the count landed exactly on the catchup floor.
    --only-missing re-fetches and predicts only races not already stored, so
    it's cheap and idempotent, and never re-picks a race already locked."""
    await _run_script("nightly_predict_all.py", ["--only-missing"])


async def job_nightly_accuracy() -> None:
    await _run_script("nightly_accuracy.py")


async def job_nightly_reflect() -> None:
    await _run_script("nightly_reflect.py")


async def job_nightly_recalibration() -> None:
    await _run_script("nightly_recalibration.py")


async def job_score_lessons() -> None:
    await _run_script("score_lessons.py")


async def job_daily_invariants() -> None:
    await _run_script("daily_invariants.py")


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


# --- predict_all catchup (self-healing) ----------------------------------
# A real run writes a row per race (~140–170/day on weekends, ~30–60 on
# weekdays). Anything under 10 by mid-morning is "almost certainly missed" —
# the only days with under 10 NA races are major US holidays, and re-firing
# on those is harmless (idempotent via on_conflict_do_nothing).
_PREDICT_ALL_HEALTHY_THRESHOLD = 10

# Cooldown between predict_all launches. A full run takes ~15 min; if it
# fails (e.g., Haiku rate-limited) and writes < threshold rows, the
# every-15-min catchup would otherwise re-fire it immediately. 60 min lets a
# real run finish, while still allowing ~5 retry windows per 8-hour catchup
# band for genuinely catastrophic failures. In-memory state resets on
# container restart, which is desirable.
_PREDICT_ALL_COOLDOWN_MIN = 60
_predict_all_last_attempt: datetime.datetime | None = None

# Hard ceiling on catchup launches per day. The 60-min cooldown alone still
# permits ~8 full-slate runs across the 8-hour band; at ~$2.75 a slate that is
# ~$22/day of silent re-spend when a run keeps failing for a NON-cost reason
# (upstream feed short, DB write error). Three attempts is enough to ride out a
# transient failure; beyond that the run is broken and re-firing only burns
# credits. Resets daily (and on container restart, which is desirable).
#
# --only-missing does NOT make this ceiling redundant: it skips races that
# already have a race_predictions row, and the failure mode this guards against
# is precisely the one where no row gets written (nightly_predict_all.py logs
# "DB write failed" and continues), so every retry re-analyzes and re-pays for
# the whole slate. Restored after being removed on that mistaken reasoning.
_PREDICT_ALL_MAX_ATTEMPTS_PER_DAY = 3
_predict_all_attempts_today: int = 0
_predict_all_attempts_date: "datetime.date | None" = None

# A catchup awaits the subprocess to completion, and one run can outlive the
# 60-min cooldown (45-min batch timeout + cancel drain + a sync fallback over
# ~150 races). Without this flag the next 15-min tick launches a SECOND
# nightly_predict_all on top of the one still running and pays for the slate
# twice. This refuses nothing: the in-flight run is already doing the work, and
# the next tick after it finishes re-evaluates from scratch.
_predict_all_running: bool = False


async def job_predict_all_catchup() -> None:
    """Self-healing predict-all check. Runs every 15 min between 8 AM–4 PM ET.

    Fires nightly_predict_all if today has fewer than
    _PREDICT_ALL_HEALTHY_THRESHOLD auto_daily rows AND no predict_all attempt
    has fired in the last _PREDICT_ALL_COOLDOWN_MIN minutes.
    """
    global _predict_all_last_attempt, _predict_all_running
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import func, select

    from app.core import database as _db
    from app.models.accuracy import RacePrediction

    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)
    if now_et.hour < 8 or now_et.hour >= 16:
        return

    # A previous catchup is still executing — let it finish rather than paying
    # for a duplicate concurrent slate.
    if _predict_all_running:
        log.info("[scheduler] predict_all catchup already running — skipping this tick")
        return

    if _predict_all_last_attempt is not None:
        age_min = (datetime.now(timezone.utc) - _predict_all_last_attempt).total_seconds() / 60
        if age_min < _PREDICT_ALL_COOLDOWN_MIN:
            return

    # Daily attempt ceiling — stops an endlessly-failing run from re-billing
    # the full slate every cooldown window.
    global _predict_all_attempts_today, _predict_all_attempts_date
    _today_et = datetime.now(et).date()
    if _predict_all_attempts_date != _today_et:
        _predict_all_attempts_date = _today_et
        _predict_all_attempts_today = 0
    if _predict_all_attempts_today >= _PREDICT_ALL_MAX_ATTEMPTS_PER_DAY:
        log.error(
            "[scheduler] predict_all catchup exhausted %d attempts today — "
            "not re-firing. Slate is failing for a non-transient reason; "
            "investigate rather than letting it re-bill.",
            _PREDICT_ALL_MAX_ATTEMPTS_PER_DAY,
        )
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
    _predict_all_attempts_today += 1
    # --only-missing skips races that already have a row for today, so a re-fire
    # pays only for what is genuinely missing. It does NOT replace the attempt
    # ceiling above: a race whose DB write failed leaves no row, so that failure
    # mode still re-buys the whole slate on every retry.
    _predict_all_running = True
    try:
        await _run_script("nightly_predict_all.py", ["--only-missing"])
    finally:
        _predict_all_running = False


# --- accuracy catchup (self-healing) -------------------------------------
# Accuracy is the most user-visible nightly: it powers the morning briefing
# email and the top-right stats. A missed fire is a felt outage, so we
# catchup more eagerly than predict_all.
_ACCURACY_CATCHUP_COOLDOWN_MIN = 60
_accuracy_last_attempt: datetime.datetime | None = None


async def job_accuracy_catchup() -> None:
    """Self-healing accuracy check. Runs every 30 min between 10 UTC and 14 UTC.

    Fires nightly_accuracy.py if yesterday's daily_accuracy_reports row is
    missing OR exists but email_sent=False. Idempotent: the script's own
    result_fetched=False filter prevents double-settling, and the report
    row upserts. Cooldown stops back-to-back fires when one is still in
    flight (a full accuracy run can take 2–3 minutes).
    """
    global _accuracy_last_attempt
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.core import database as _db
    from app.models.accuracy import DailyAccuracyReport

    now_utc = datetime.now(timezone.utc)
    if not (10 <= now_utc.hour < 14):
        return

    if _accuracy_last_attempt is not None:
        age_min = (now_utc - _accuracy_last_attempt).total_seconds() / 60
        if age_min < _ACCURACY_CATCHUP_COOLDOWN_MIN:
            return

    yesterday = now_utc.date() - timedelta(days=1)
    try:
        async with _db._AsyncSessionLocal() as db:
            result = await db.execute(
                select(DailyAccuracyReport).where(
                    DailyAccuracyReport.report_date == yesterday
                )
            )
            existing = result.scalar_one_or_none()
    except Exception as e:
        log.warning(f"[scheduler] accuracy catchup db check failed: {e}")
        return

    if existing is not None and existing.email_sent:
        return  # Done for yesterday.

    state = "missing" if existing is None else "report-saved-but-email-failed"
    print(
        f"[scheduler] catchup: accuracy for {yesterday.isoformat()} {state} "
        f"— firing nightly_accuracy.py",
        flush=True,
    )
    _accuracy_last_attempt = now_utc
    await _run_script("nightly_accuracy.py")


# --- reflect catchup (self-healing) --------------------------------------
# Reflect is the learning loop — the most important nightly — yet it was the
# only nightly with NO self-heal. A single disrupted 14:30 fire vanished with no
# retry (the 597 guardrail caught 2026-06-07 going unreflected). This catchup
# re-fires reflect if yesterday's settled NA races have zero reflections.
# Idempotent: nightly_reflect filters reflection IS NULL.
_REFLECT_CATCHUP_COOLDOWN_MIN = 60
_reflect_last_attempt: "datetime.datetime | None" = None


async def job_reflect_catchup() -> None:
    """Self-healing reflect check. Runs every 30 min from 15:00 UTC through the
    end of the UTC day.

    Reflect is scheduled at 14:30 UTC (after accuracy settles at 10:00). If that
    fire is missed or killed, this re-fires it so the learning loop never silently
    skips a day. The window runs to 23:59 UTC so a miss discovered late at night
    still self-recovers same-day — after 00:00 UTC "yesterday" rolls forward and
    the missed day is no longer the target. Fires only when yesterday has settled
    NA races but zero reflections — the exact condition the 597 smoke alert flags.
    """
    global _reflect_last_attempt
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select

    from app.core import database as _db
    from app.models.accuracy import RacePrediction

    now_utc = datetime.now(timezone.utc)
    if now_utc.hour < 15:
        return

    if _reflect_last_attempt is not None:
        age_min = (now_utc - _reflect_last_attempt).total_seconds() / 60
        if age_min < _REFLECT_CATCHUP_COOLDOWN_MIN:
            return

    yesterday = now_utc.date() - timedelta(days=1)
    try:
        async with _db._AsyncSessionLocal() as db:
            settled = await db.scalar(
                select(func.count(RacePrediction.id)).where(
                    RacePrediction.race_date == yesterday,
                    RacePrediction.result_fetched == True,  # noqa: E712
                    (RacePrediction.region == "na") | (RacePrediction.region.is_(None)),
                )
            )
            reflected = await db.scalar(
                select(func.count(RacePrediction.id)).where(
                    RacePrediction.race_date == yesterday,
                    RacePrediction.result_fetched == True,  # noqa: E712
                    RacePrediction.reflection.is_not(None),
                )
            )
    except Exception as e:
        log.warning(f"[scheduler] reflect catchup db check failed: {e}")
        return

    if not settled or (reflected or 0) > 0:
        return  # nothing to reflect yet, or reflection already happened

    print(
        f"[scheduler] catchup: {settled} settled races for {yesterday.isoformat()} "
        f"but 0 reflections — firing nightly_reflect.py",
        flush=True,
    )
    _reflect_last_attempt = now_utc
    await _run_script("nightly_reflect.py", ["--date", yesterday.isoformat()])


def create_scheduler() -> AsyncIOScheduler | None:
    """Create and return the scheduler, or None if not running as the backend.

    Returning None lets main.py treat scheduling as optional, which is the
    correct behavior for any sibling service that boots start.sh by accident.
    """
    svc = os.getenv("RAILWAY_SERVICE_NAME", "")
    if svc and svc != "backend":
        print(
            f"[scheduler] RAILWAY_SERVICE_NAME='{svc}' — not the backend, "
            f"skipping scheduler to avoid double-fires",
            flush=True,
        )
        return None

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Catchup fires 30s after startup (so deploys self-heal immediately) and
    # then every 15 min. The job itself bails outside the 8 AM–4 PM ET window.
    catchup_first_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=30)

    # Nightly jobs — misfire_grace_time=3600 means a backend that restarts
    # within an hour of the scheduled time still fires the missed job.
    scheduler.add_job(
        job_nightly_recalibration,
        CronTrigger(hour=3, minute=30),
        id="nightly_recalibration",
        name="Nightly recalibration (03:30 UTC)",
        misfire_grace_time=3600,
        max_instances=1,
        coalesce=True,
    )
    # Reflect MUST run after accuracy settles yesterday's races. Accuracy fires
    # at 10:00 UTC and its catchup retries through 14:00 UTC, so reflect at 14:30
    # is guaranteed to see settled data. The old 04:00 slot ran 6h BEFORE the
    # data it needs existed, so it found "no settled predictions" every night
    # and the learning loop never advanced.
    scheduler.add_job(
        job_nightly_reflect,
        CronTrigger(hour=14, minute=30),
        id="nightly_reflect",
        name="Nightly reflect (14:30 UTC, after accuracy settles)",
        misfire_grace_time=3600,
        max_instances=1,
        coalesce=True,
    )
    # Scores each lesson against contemporaneous races in its own scope and
    # retires the ones measurably worse than no lesson. Runs after reflect has
    # written the night's playbook, so a lesson minted today is scoreable from
    # tomorrow rather than a day later.
    # Asserts production is doing the right thing, not merely that it is up.
    # Runs after accuracy has settled yesterday's slate, so coverage and grading
    # checks see a complete day.
    scheduler.add_job(
        job_daily_invariants,
        CronTrigger(hour=16, minute=0),
        id="daily_invariants",
        name="Daily production invariants (16:00 UTC)",
        misfire_grace_time=3600,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_score_lessons,
        CronTrigger(hour=15, minute=30),
        id="score_lessons",
        name="Score + retire lessons (15:30 UTC, after reflect)",
        misfire_grace_time=3600,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        job_nightly_accuracy,
        CronTrigger(hour=10, minute=0),
        id="nightly_accuracy",
        name="Nightly accuracy + morning briefing email (10:00 UTC / 6 AM ET)",
        misfire_grace_time=3600,
        max_instances=1,
        coalesce=True,
    )
    # Catchup for accuracy — eager because users see the morning email.
    scheduler.add_job(
        job_accuracy_catchup,
        IntervalTrigger(minutes=30, start_date=catchup_first_run),
        id="accuracy_catchup",
        name="Accuracy self-heal (every 30 min, 10–14 UTC)",
        max_instances=1,
        coalesce=True,
    )

    # Catchup for reflect — the learning loop must never silently skip a day.
    scheduler.add_job(
        job_reflect_catchup,
        IntervalTrigger(minutes=30, start_date=catchup_first_run),
        id="reflect_catchup",
        name="Reflect self-heal (every 30 min, 15 UTC–end of day)",
        max_instances=1,
        coalesce=True,
    )

    # predict_all is fired only via catchup — the catchup runs from 8 AM ET
    # onward, so the 12 UTC fire happens at the very first catchup tick.
    scheduler.add_job(
        job_predict_all_catchup,
        IntervalTrigger(minutes=15, start_date=catchup_first_run),
        id="predict_all_catchup",
        name="Predict-all self-heal (every 15 min, 8 AM–4 PM ET)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(job_predict_all_second_pass, CronTrigger(hour=15, minute=0), id="predict_all_second_pass", name="Predict-all second pass — only-missing (11 AM ET)", misfire_grace_time=3600)
    # Watchlist alerts after each predict pass (deduped) — 12:45 & 15:15 UTC.
    scheduler.add_job(job_watchlist_alerts, CronTrigger(hour=12, minute=45), id="watchlist_alerts_am", name="Watchlist alerts (8:45 AM ET)", misfire_grace_time=3600)
    scheduler.add_job(job_watchlist_alerts, CronTrigger(hour=15, minute=15), id="watchlist_alerts_mid", name="Watchlist alerts (11:15 AM ET)", misfire_grace_time=3600)
    scheduler.add_job(job_race_alerts, IntervalTrigger(minutes=5), id="race_alerts", name="Race alerts (every 5 min)")
    scheduler.add_job(job_smoke_check, IntervalTrigger(minutes=5), id="smoke_check", name="Prod smoke check (every 5 min)")

    return scheduler
