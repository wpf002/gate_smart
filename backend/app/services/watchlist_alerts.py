"""
Watchlist alerts — notify each user when a followed horse/trainer/jockey is
entered in an upcoming race. Deduped per (user, entity, race) so a user is
pinged once, not on every run. Targets the user via OneSignal
include_external_user_ids (the frontend links external_user_id = user_id).
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_DEDUP_TTL = 20 * 3600  # ~a racing day; resets before the next card


async def check_watchlist_alerts() -> None:
    from sqlalchemy import select

    from app.core import database as _db
    from app.core.cache import cache_get, cache_set
    from app.api.routes.watchlist import build_watchlist_matches
    from app.models.watchlist import WatchlistItem
    from app.services.notifications import send_watchlist_notification
    from app.services.racing_api import get_na_racecards_full

    try:
        async with _db._AsyncSessionLocal() as db:
            rows = await db.execute(select(WatchlistItem))
            items = list(rows.scalars().all())
    except Exception as e:
        log.warning(f"[watchlist_alerts] load failed: {e}")
        return
    if not items:
        return

    # Fetch today's card once (shared across all users).
    try:
        today = await get_na_racecards_full("today")
        cards_by_day = {"today": today.get("racecards", [])}
    except Exception as e:
        log.warning(f"[watchlist_alerts] racecards fetch failed: {e}")
        return

    by_user: dict[int, list] = defaultdict(list)
    for it in items:
        by_user[it.user_id].append(it)

    now = datetime.now(timezone.utc)
    sent = 0
    for user_id, user_items in by_user.items():
        matches = build_watchlist_matches(user_items, cards_by_day)
        for m in matches:
            # Only alert for races that haven't gone off yet.
            off = m.get("off_dt")
            if off:
                try:
                    if datetime.fromisoformat(off) <= now:
                        continue
                except ValueError:
                    pass
            dedup_key = f"wl_alert:{user_id}:{m['entity_type']}:{m['entity_label']}:{m['race_id']}"
            try:
                if await cache_get(dedup_key):
                    continue
            except Exception:
                pass
            try:
                await send_watchlist_notification(
                    external_user_id=str(user_id),
                    entity_label=m["entity_label"],
                    entity_type=m["entity_type"],
                    horse_name=m.get("horse_name") or "",
                    track_name=m.get("course") or "",
                    race_name=m.get("race_name") or "",
                    post_time=m.get("post_time_et"),
                )
                await cache_set(dedup_key, "1", ex=_DEDUP_TTL)
                sent += 1
            except Exception as e:
                log.warning(f"[watchlist_alerts] send failed for user {user_id}: {e}")

    if sent:
        print(f"[watchlist_alerts] sent {sent} watchlist notifications", flush=True)
