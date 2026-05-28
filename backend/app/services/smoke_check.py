"""
Production smoke check — runs every 5 minutes from the scheduler.

Hits the same endpoints the UI loads on first paint. Emails on state
transitions (healthy→fail, fail→recovered) and re-alerts once per 30 min
while still failing, so a single transient blip doesn't spam the inbox
and a sustained outage doesn't go silent if the first email is lost.
"""
import datetime
import logging
import os

import httpx

from app.core.config import settings
from app.services.email_service import send_daily_report

log = logging.getLogger(__name__)

FRONTEND = "https://gate-smart.up.railway.app"
BACKEND = "https://backend-production-15e941.up.railway.app"

# Smoke checks are skipped in dev so they don't fire during local work.
_ENABLED = os.getenv("ENVIRONMENT", "development") == "production"

# In-process state. Resets on container restart, which is fine — a restart
# either fixes the problem (next failure re-alerts) or doesn't (next tick
# still detects failure and alerts as a new transition).
_last_status: str | None = None  # "ok" | "fail"
_last_alert_at: datetime.datetime | None = None
_RE_ALERT_AFTER = datetime.timedelta(minutes=30)

# Accuracy is considered stale if yesterday's daily_accuracy_reports row is
# missing or unsent by this UTC hour. 14 UTC gives the 10 UTC scheduled fire
# plus 4 hours of 30-min catchup retries to land — anything later is real.
_ACCURACY_STALE_AFTER_HOUR_UTC = 14

# Reflect runs at 14:30 UTC; by 16 UTC every settled race should have a
# reflection. Settled races but zero reflections = the learning loop silently
# produced nothing — exactly the failure that went unnoticed for weeks.
_REFLECT_STALE_AFTER_HOUR_UTC = 16


def _checks() -> list[tuple[str, str]]:
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    return [
        ("Backend health", f"{BACKEND}/health"),
        ("Frontend shell", f"{FRONTEND}/"),
        ("Races today (proxy)", f"{FRONTEND}/api/races/today"),
        (f"Races {tomorrow} (proxy)", f"{FRONTEND}/api/races/date/{tomorrow}"),
    ]


async def _check_accuracy_freshness() -> tuple[str, int] | None:
    """Return (label, code) tuple if yesterday's accuracy report is stale.

    Code mapping: 0 = check raised, 599 = row missing, 598 = row exists but
    email_sent=False. None means healthy (or it's too early in the day to
    judge). The HTTP-style code lets the existing failure formatter render
    this row uniformly with the URL checks.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.hour < _ACCURACY_STALE_AFTER_HOUR_UTC:
        return None

    # Keep this a date object — DailyAccuracyReport.report_date is a DATE column
    # and asyncpg won't coerce a str, so passing .isoformat() here raises
    # "operator does not exist: date = character varying" and the check reads as
    # a false failure on every run.
    yesterday = now_utc.date() - datetime.timedelta(days=1)
    try:
        from sqlalchemy import select

        from app.core import database as _db
        from app.models.accuracy import DailyAccuracyReport

        async with _db._AsyncSessionLocal() as db:
            result = await db.execute(
                select(DailyAccuracyReport).where(
                    DailyAccuracyReport.report_date == yesterday
                )
            )
            row = result.scalar_one_or_none()
    except Exception as e:
        log.warning(f"[smoke] accuracy freshness check raised: {e}")
        return (f"Accuracy freshness check ({yesterday})", 0)

    if row is None:
        return (f"No accuracy report for {yesterday}", 599)
    if not row.email_sent:
        return (f"Accuracy report for {yesterday} exists but email not sent", 598)
    return None


async def _check_reflect_freshness() -> tuple[str, int] | None:
    """Return (label, code) if yesterday's settled races never got reflected.

    Code mapping: 0 = check raised, 597 = settled races exist but 0 reflections.
    None means healthy (or too early to judge). This is the guardrail for the
    learning loop: if reflect silently produces nothing, this fires an alert
    instead of letting it rot unnoticed.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.hour < _REFLECT_STALE_AFTER_HOUR_UTC:
        return None

    yesterday = now_utc.date() - datetime.timedelta(days=1)
    try:
        from sqlalchemy import func, select

        from app.core import database as _db
        from app.models.accuracy import RacePrediction

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
        log.warning(f"[smoke] reflect freshness check raised: {e}")
        return (f"Reflect freshness check ({yesterday})", 0)

    if settled and not reflected:
        return (
            f"{settled} settled races for {yesterday} but 0 reflections — "
            "reflect produced nothing",
            597,
        )
    return None


async def _hit(url: str) -> tuple[int, float]:
    start = datetime.datetime.now()
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            resp = await client.get(url)
        elapsed = (datetime.datetime.now() - start).total_seconds()
        return resp.status_code, elapsed
    except Exception as e:
        elapsed = (datetime.datetime.now() - start).total_seconds()
        log.warning(f"[smoke] {url} raised {type(e).__name__}: {e}")
        return 0, elapsed


async def run_smoke_check() -> None:
    global _last_status, _last_alert_at

    if not _ENABLED:
        return

    results: list[tuple[str, str, int, float]] = []
    failures: list[tuple[str, str, int]] = []
    for label, url in _checks():
        code, elapsed = await _hit(url)
        results.append((label, url, code, elapsed))
        if code != 200:
            failures.append((label, url, code))

    accuracy_stale = await _check_accuracy_freshness()
    if accuracy_stale is not None:
        label, code = accuracy_stale
        results.append((label, "db://daily_accuracy_reports", code, 0.0))
        failures.append((label, "db://daily_accuracy_reports", code))

    reflect_stale = await _check_reflect_freshness()
    if reflect_stale is not None:
        label, code = reflect_stale
        results.append((label, "db://race_predictions.reflection", code, 0.0))
        failures.append((label, "db://race_predictions.reflection", code))

    now = datetime.datetime.utcnow()
    current = "fail" if failures else "ok"
    print(
        f"[smoke] {now.isoformat()}Z status={current} "
        f"({len(failures)}/{len(results)} failing)",
        flush=True,
    )

    transitioned = _last_status != current
    stale_alert = (
        current == "fail"
        and _last_alert_at is not None
        and now - _last_alert_at >= _RE_ALERT_AFTER
    )

    if transitioned or stale_alert:
        if current == "fail":
            subject = f"[GateSmart] Prod regression — {len(failures)} check(s) failing"
            lines = [f"Detected at {now.isoformat()}Z\n", "Failing checks:"]
            for label, url, code in failures:
                lines.append(f"  - {label}: HTTP {code} {url}")
            lines.append("\nAll checks:")
            for label, url, code, elapsed in results:
                mark = "OK  " if code == 200 else "FAIL"
                lines.append(f"  [{mark}] {code}  {elapsed:.2f}s  {label}  {url}")
            body = "\n".join(lines)
            html = "<pre>" + body.replace("<", "&lt;") + "</pre>"
            await send_daily_report(subject=subject, html_body=html, text_body=body)
            _last_alert_at = now
        else:
            subject = "[GateSmart] Prod recovered"
            body = (
                f"All checks green again at {now.isoformat()}Z.\n\n"
                + "\n".join(
                    f"  [OK] {code}  {elapsed:.2f}s  {label}"
                    for label, _u, code, elapsed in results
                )
            )
            html = "<pre>" + body + "</pre>"
            await send_daily_report(subject=subject, html_body=html, text_body=body)
            _last_alert_at = None

    _last_status = current
