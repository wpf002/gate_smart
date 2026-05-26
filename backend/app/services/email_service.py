"""
Email service — sends daily Secretariat accuracy digest via Resend API.
"""
import asyncio

import httpx

from app.core.config import settings


async def send_daily_report(
    subject: str,
    html_body: str,
    text_body: str,
    to_email: str = None,
) -> bool:
    """
    Send the daily accuracy email via Resend HTTP API. Retries up to 3 times on
    transient failure (network error, 5xx, 429) with exponential backoff.
    `to_email` and the DAILY_REPORT_EMAIL setting accept a comma-separated list.
    Returns True on success, False after all retries exhausted. On final failure
    prints a [DIGEST EMAIL FAILED] banner so Railway log scrapers can alert.
    """
    raw = to_email or settings.DAILY_REPORT_EMAIL
    recipients = [addr.strip() for addr in raw.split(",") if addr.strip()]

    if not recipients:
        print("[DIGEST EMAIL FAILED] No daily-report recipients configured — skipping send")
        return False

    if not settings.RESEND_API_KEY:
        print("[DIGEST EMAIL FAILED] RESEND_API_KEY not set — skipping send")
        print(f"Subject: {subject}")
        print(f"Body preview:\n{text_body[:500]}")
        return False

    # Retry on transient failures. 4xx (except 429) are permanent — bail immediately
    # so we don't waste attempts on bad recipient / bad payload errors.
    max_attempts = 3
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    json={
                        "from": "Secretariat <onboarding@resend.dev>",
                        "to": recipients,
                        "subject": subject,
                        "html": html_body,
                        "text": text_body,
                    },
                )
            if resp.status_code in (200, 201):
                print(f"Daily report sent to {', '.join(recipients)} (Resend id={resp.json().get('id')})")
                return True
            # 4xx other than 429 won't succeed on retry (auth, validation, sandbox-recipient)
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                print(f"[DIGEST EMAIL FAILED] Resend API permanent error {resp.status_code}: {resp.text[:300]}")
                return False
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"

        if attempt < max_attempts:
            backoff = 2 ** attempt  # 2s, 4s
            print(f"[email] attempt {attempt}/{max_attempts} failed ({last_error}) — retrying in {backoff}s")
            await asyncio.sleep(backoff)

    print(f"[DIGEST EMAIL FAILED] all {max_attempts} attempts exhausted — last error: {last_error}")
    return False
