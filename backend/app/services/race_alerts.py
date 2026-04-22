"""
Race alerts service — sends push notifications ~30 minutes before post time
when Secretariat has a stored auto_daily prediction.

Runs every 5 minutes via the APScheduler interval job.
"""
import datetime
import logging

log = logging.getLogger(__name__)


def _now_et() -> datetime.datetime:
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("America/New_York")
        return datetime.datetime.now(tz)
    except Exception:
        # Fallback: UTC-4 (EDT) — close enough for alert window purposes
        return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)


async def check_and_send_race_alerts() -> None:
    """
    Runs every 5 minutes.
    Finds races whose post_time_et falls 25-35 minutes from now.
    For each unsent auto_daily prediction in that window, fires a OneSignal
    notification to all subscribers and marks alert_sent=True.
    """
    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import RacePrediction
        from app.services.notifications import send_race_alert_notification
        from sqlalchemy import select, update as _update

        if not _AsyncSessionLocal:
            return

        now_et = _now_et()
        today = now_et.date()

        window_start = (now_et + datetime.timedelta(minutes=25)).strftime("%H:%M")
        window_end = (now_et + datetime.timedelta(minutes=35)).strftime("%H:%M")

        async with _AsyncSessionLocal() as db:
            result = await db.execute(
                select(RacePrediction).where(
                    RacePrediction.race_date == today,
                    RacePrediction.result_fetched == False,  # noqa: E712
                    RacePrediction.alert_sent == False,  # noqa: E712
                    RacePrediction.analysis_mode == "auto_daily",
                    RacePrediction.post_time_et.is_not(None),
                    RacePrediction.post_time_et >= window_start,
                    RacePrediction.post_time_et <= window_end,
                )
            )
            predictions = result.scalars().all()

            for pred in predictions:
                try:
                    horse_name = pred.predicted_first or "TBD"
                    track = pred.track_code or "Unknown Track"
                    race_name = pred.race_name or f"Race at {track}"
                    post_time = pred.post_time_et or ""

                    await send_race_alert_notification(
                        track_name=track,
                        race_name=race_name,
                        race_number="",
                        horse_name=horse_name,
                        post_time=post_time,
                    )

                    await db.execute(
                        _update(RacePrediction)
                        .where(RacePrediction.id == pred.id)
                        .values(alert_sent=True)
                    )
                    log.info(f"[race_alerts] Sent alert for {race_name} at {track} ({post_time}), pick={horse_name}")
                except Exception as e:
                    log.warning(f"[race_alerts] Failed alert for prediction {pred.id}: {e}")
                    continue

            await db.commit()

    except Exception as e:
        log.warning(f"[race_alerts] check_and_send_race_alerts error: {e}")
