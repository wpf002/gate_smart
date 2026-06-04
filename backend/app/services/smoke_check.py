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

# Predict-all slate completeness — the guardrail for the Morning Line itself.
# predict_all is fired by the 8 AM ET catchup; a full run takes ~15 min and the
# catchup keeps retrying through the morning. By 14 UTC (10 AM ET) a healthy day
# has far more than this many picks — under it means the Morning Line is
# effectively missing. Threshold matches the scheduler catchup so light/holiday
# cards don't false-alarm. THIS is the check that means you never again have to
# be the one who discovers the Morning Line is blank.
_PREDICT_STALE_AFTER_HOUR_UTC = 14
_PREDICT_MIN_SLATE = 10

# Anthropic API health probe. A tiny 1-token call surfaces a credit/auth
# blackout BEFORE it silently wipes a day of picks (cf. the 2026-06-01 credit
# outage that went unnoticed for two days). Probed at most every 30 min; the
# verdict is cached between probes so the alert state stays stable and cheap.
_API_PROBE_EVERY = datetime.timedelta(minutes=30)
_API_PROBE_MODEL = "claude-haiku-4-5-20251001"
_last_api_probe_at: datetime.datetime | None = None
_last_api_verdict: "tuple[str, int] | None" = None


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


async def _check_predict_all_freshness() -> tuple[str, int] | None:
    """Return (label, code) if today's Morning Line slate is missing/short.

    Code 596 = far fewer than a real day's predictions by the cutoff hour.
    None means healthy (or too early to judge). The scheduler's catchup is
    already re-firing predict_all in the background; this is the alert that
    makes a stuck slate visible instead of silent.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if now_utc.hour < _PREDICT_STALE_AFTER_HOUR_UTC:
        return None

    today = now_utc.date()
    try:
        from sqlalchemy import func, select

        from app.core import database as _db
        from app.models.accuracy import RacePrediction

        async with _db._AsyncSessionLocal() as db:
            count = await db.scalar(
                select(func.count(RacePrediction.id)).where(
                    RacePrediction.race_date == today,
                    RacePrediction.analysis_mode == "auto_daily",
                    RacePrediction.user_id.is_(None),
                )
            )
    except Exception as e:
        log.warning(f"[smoke] predict_all freshness check raised: {e}")
        return (f"Predict-all freshness check ({today})", 0)

    if (count or 0) < _PREDICT_MIN_SLATE:
        return (
            f"Only {count or 0} predictions for {today} by {now_utc.hour:02d}:00 UTC "
            "— Morning Line slate is missing/short",
            596,
        )
    return None


def _classify_api_error(message: str, status_code: int | None) -> tuple[str, int] | None:
    """Pure classifier: map an Anthropic error to an actionable alert, or None.

    Only definitive, actionable failures (credit exhausted, auth) alert — a
    transient network blip returns None so we don't false-alarm (a sustained
    outage is caught by the slate-completeness check anyway).
    """
    msg = (message or "").lower()
    if any(s in msg for s in ("credit balance", "too low", "purchase credits", "plans & billing", "billing")):
        return (
            "Anthropic API: credit balance too low — top up at "
            "console.anthropic.com (Plans & Billing)",
            595,
        )
    if status_code in (401, 403) or "authentication" in msg or "x-api-key" in msg:
        return ("Anthropic API: authentication failed — check ANTHROPIC_API_KEY", 595)
    return None


async def _check_api_health() -> tuple[str, int] | None:
    """Probe the Anthropic API with a 1-token call; alert on credit/auth death.

    Throttled to once per _API_PROBE_EVERY; verdict cached between probes.
    """
    global _last_api_probe_at, _last_api_verdict
    now = datetime.datetime.now(datetime.timezone.utc)
    if _last_api_probe_at is not None and now - _last_api_probe_at < _API_PROBE_EVERY:
        return _last_api_verdict

    _last_api_probe_at = now
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        await client.messages.create(
            model=_API_PROBE_MODEL,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        _last_api_verdict = None
    except Exception as e:  # noqa: BLE001 — probe must never crash the smoke loop
        _last_api_verdict = _classify_api_error(str(e), getattr(e, "status_code", None))
        if _last_api_verdict is None:
            log.warning(f"[smoke] api health probe error (not alerting): {type(e).__name__}: {e}")
    return _last_api_verdict


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

    predict_stale = await _check_predict_all_freshness()
    if predict_stale is not None:
        label, code = predict_stale
        results.append((label, "db://race_predictions", code, 0.0))
        failures.append((label, "db://race_predictions", code))

    api_health = await _check_api_health()
    if api_health is not None:
        label, code = api_health
        results.append((label, "anthropic://messages", code, 0.0))
        failures.append((label, "anthropic://messages", code))

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
