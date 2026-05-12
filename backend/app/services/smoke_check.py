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


def _checks() -> list[tuple[str, str]]:
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    return [
        ("Backend health", f"{BACKEND}/health"),
        ("Frontend shell", f"{FRONTEND}/"),
        ("Races today (proxy)", f"{FRONTEND}/api/races/today"),
        (f"Races {tomorrow} (proxy)", f"{FRONTEND}/api/races/date/{tomorrow}"),
    ]


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
