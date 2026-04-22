import httpx
from app.core.config import settings

ONESIGNAL_API = "https://onesignal.com/api/v1"


async def send_value_alert_notification(
    horse_name: str,
    race_name: str,
    course: str,
    current_odds: str,
    fair_odds: str,
    value_percent: float,
    alert_level: str,
    external_user_ids: list[str] = None,
) -> dict:
    if not settings.ONESIGNAL_APP_ID or not settings.ONESIGNAL_API_KEY:
        return {"skipped": True, "reason": "OneSignal not configured"}

    level_emoji = {"strong": "🔥", "moderate": "⚡", "watch": "👀"}
    emoji = level_emoji.get(alert_level, "⚡")

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "headings": {"en": f"{emoji} Value Alert — {horse_name}"},
        "contents": {
            "en": (
                f"{horse_name} at {current_odds} — "
                f"Secretariat's fair price is {fair_odds}. "
                f"{round(value_percent)}% overlay at {course}."
            )
        },
        "data": {
            "type": "value_alert",
            "horse_name": horse_name,
            "alert_level": alert_level,
        },
        "included_segments": ["All"] if not external_user_ids else [],
    }
    if external_user_ids:
        payload["include_external_user_ids"] = external_user_ids

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{ONESIGNAL_API}/notifications",
            json=payload,
            headers={
                "Authorization": f"Basic {settings.ONESIGNAL_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        return resp.json()


async def send_race_alert_notification(
    track_name: str,
    race_name: str,
    race_number: str,
    horse_name: str,
    post_time: str,
) -> dict:
    if not settings.ONESIGNAL_APP_ID or not settings.ONESIGNAL_API_KEY:
        return {"skipped": True, "reason": "OneSignal not configured"}

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "headings": {"en": f"🏇 Race Alert — {track_name}"},
        "contents": {
            "en": (
                f"{race_name} posts in ~30 min. "
                f"Secretariat's pick: {horse_name}."
            )
        },
        "data": {
            "type": "race_alert",
            "race_name": race_name,
            "track": track_name,
            "horse": horse_name,
            "post_time": post_time,
        },
        "included_segments": ["All"],
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{ONESIGNAL_API}/notifications",
            json=payload,
            headers={
                "Authorization": f"Basic {settings.ONESIGNAL_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        return resp.json()


async def send_race_reminder_notification(
    race_name: str,
    course: str,
    post_time: str,
    external_user_ids: list[str] = None,
) -> dict:
    if not settings.ONESIGNAL_APP_ID or not settings.ONESIGNAL_API_KEY:
        return {"skipped": True, "reason": "OneSignal not configured"}

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "headings": {"en": f"🏇 Race Starting Soon — {course}"},
        "contents": {
            "en": (
                f"{race_name} posts at {post_time}. "
                f"Time to finalise your selections."
            )
        },
        "data": {"type": "race_reminder", "race_name": race_name},
        "included_segments": ["All"] if not external_user_ids else [],
    }
    if external_user_ids:
        payload["include_external_user_ids"] = external_user_ids

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{ONESIGNAL_API}/notifications",
            json=payload,
            headers={
                "Authorization": f"Basic {settings.ONESIGNAL_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        return resp.json()
