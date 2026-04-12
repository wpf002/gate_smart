"""
Email service — sends daily Secretariat accuracy digest via Gmail SMTP.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


async def send_daily_report(
    subject: str,
    html_body: str,
    text_body: str,
    to_email: str = None,
) -> bool:
    """
    Send the daily accuracy email via Gmail SMTP SSL.
    Returns True on success, False on failure.
    If GMAIL_USER or GMAIL_APP_PASSWORD are not set, prints a preview instead.
    """
    recipient = to_email or settings.DAILY_REPORT_EMAIL

    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASSWORD:
        print("Email not configured — skipping send")
        print(f"Subject: {subject}")
        print(f"Body preview:\n{text_body[:500]}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Secretariat <{settings.GMAIL_USER}>"
        msg["To"] = recipient

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASSWORD)
            server.sendmail(settings.GMAIL_USER, recipient, msg.as_string())

        print(f"Daily report sent to {recipient}")
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False
