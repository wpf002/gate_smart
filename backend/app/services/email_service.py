"""
Email service — sends daily Secretariat accuracy digest via Resend API.
"""
import httpx

from app.core.config import settings


async def send_daily_report(
    subject: str,
    html_body: str,
    text_body: str,
    to_email: str = None,
) -> bool:
    """
    Send the daily accuracy email via Resend HTTP API.
    `to_email` and the DAILY_REPORT_EMAIL setting accept a comma-separated list.
    Returns True on success, False on failure.
    """
    raw = to_email or settings.DAILY_REPORT_EMAIL
    recipients = [addr.strip() for addr in raw.split(",") if addr.strip()]

    if not recipients:
        print("No daily-report recipients configured — skipping send")
        return False

    if not settings.RESEND_API_KEY:
        print("RESEND_API_KEY not set — skipping send")
        print(f"Subject: {subject}")
        print(f"Body preview:\n{text_body[:500]}")
        return False

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        else:
            print(f"Resend API error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"Email send failed: {e}")
        return False
