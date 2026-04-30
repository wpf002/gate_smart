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


def _norm_name(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ")


async def _resolve_live_pick(pred) -> tuple[str, bool]:
    """Check the live racecard for late scratches. If `predicted_first` has
    scratched, advance to the next non-scratched pick from predicted_second/
    third/fourth. Returns (horse_name, advanced_flag).

    Falls back to the stored predicted_first on any API/lookup failure — better
    to send the original alert than nothing.
    """
    from app.services.racing_api import get_race

    try:
        race = await get_race(pred.race_id)
    except Exception as e:
        log.warning(f"[race_alerts] get_race failed for {pred.race_id}: {e}")
        return pred.predicted_first or "TBD", False

    runners = race.get("runners", []) or []
    by_name = {
        _norm_name(r.get("horse") or r.get("horse_name", "")): r
        for r in runners
    }

    candidates = [
        ("first",  pred.predicted_first),
        ("second", pred.predicted_second),
        ("third",  pred.predicted_third),
        ("fourth", pred.predicted_fourth),
    ]
    for slot, name in candidates:
        if not name:
            continue
        runner = by_name.get(_norm_name(name))
        if runner is None:
            # Name not on the card at all — treat as scratched and try next
            continue
        if runner.get("scratched") or runner.get("non_runner"):
            continue
        advanced = slot != "first"
        return name, advanced

    # Everything we picked is gone — fall back to the original top pick
    return pred.predicted_first or "TBD", False


async def check_and_send_race_alerts() -> None:
    """
    Runs every 5 minutes.
    Finds races whose post_time_et falls 25-35 minutes from now.
    For each unsent auto_daily prediction in that window, checks the live
    racecard for late scratches and advances to the next live pick if
    needed, then fires a OneSignal notification and marks alert_sent=True.
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
                    horse_name, advanced = await _resolve_live_pick(pred)
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

                    update_values = {"alert_sent": True}
                    # If we advanced past a scratched top pick, persist the new pick
                    # so accuracy settling and the digest reflect what we actually called.
                    if advanced and horse_name and horse_name != pred.predicted_first:
                        update_values["predicted_first"] = horse_name
                    await db.execute(
                        _update(RacePrediction)
                        .where(RacePrediction.id == pred.id)
                        .values(**update_values)
                    )
                    suffix = " (advanced past scratch)" if advanced else ""
                    log.info(f"[race_alerts] Sent alert for {race_name} at {track} ({post_time}), pick={horse_name}{suffix}")
                except Exception as e:
                    log.warning(f"[race_alerts] Failed alert for prediction {pred.id}: {e}")
                    continue

            await db.commit()

    except Exception as e:
        log.warning(f"[race_alerts] check_and_send_race_alerts error: {e}")
