"""
Scoring, streaks and standings for pick contests.

The scoring and streak functions are pure over their inputs so they can be tested
without a database. Settlement reads the official results chart, so a pick is
graded the same day the race runs rather than waiting for the nightly job.
"""
from datetime import date, timedelta
from typing import Iterable, Optional

# A correct winner is worth 10. Beating Secretariat — you were right and it was
# wrong — adds 5. A miss scores nothing; there are no negative points, because
# the point is to reward making calls, not to punish them.
POINTS_CORRECT = 10
POINTS_BEAT_BONUS = 5


def score_pick(pick_key: str, winner_key: str, secretariat_key: Optional[str]) -> dict:
    """Grade one pick against the official winner and Secretariat's call."""
    correct = bool(pick_key) and pick_key == winner_key
    secretariat_correct = (
        None if not secretariat_key else secretariat_key == winner_key
    )
    beat = bool(correct and secretariat_correct is False)
    points = (POINTS_CORRECT if correct else 0) + (POINTS_BEAT_BONUS if beat else 0)
    return {
        "correct": correct,
        "secretariat_correct": secretariat_correct,
        "beat_secretariat": beat,
        "points": points,
    }


def pick_day_streak(pick_dates: Iterable[date], today: date) -> int:
    """Consecutive days with at least one pick, ending today or yesterday.

    Yesterday counts as still alive: a streak shouldn't read as broken at 8am
    just because today's card hasn't been picked yet.
    """
    days = set(pick_dates)
    if not days:
        return 0
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def beat_secretariat_streak(settled_in_order: Iterable[dict]) -> int:
    """Races in a row, counting back from the latest, where you beat Secretariat.

    A beat extends it. A miss ends it. A race where you and Secretariat were both
    right is a tie — it neither extends nor breaks the streak, since you didn't
    lose to it.
    """
    streak = 0
    for pick in reversed(list(settled_in_order)):
        if pick.get("beat_secretariat"):
            streak += 1
        elif not pick.get("correct"):
            break
    return streak


def best_streak(values: list[bool]) -> int:
    """Longest run of True."""
    best = run = 0
    for v in values:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


async def settle_pending_picks() -> int:
    """Grade every unsettled pick whose race has an official result. Idempotent.

    Returns how many picks were settled.
    """
    from sqlalchemy import select

    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from app.models.contest import ContestPick
    from app.services.horse_form import horse_key
    from app.services.racing_api import get_na_meet_results

    if not _db._AsyncSessionLocal:
        return 0

    async with _db._AsyncSessionLocal() as db:
        pending = list((await db.execute(
            select(ContestPick).where(
                ContestPick.settled == False,  # noqa: E712
                ContestPick.race_date <= date.today(),
            )
        )).scalars().all())
        if not pending:
            return 0

        race_ids = {p.race_id for p in pending}
        secretariat = {
            r.race_id: r.predicted_first
            for r in (await db.execute(
                select(RacePrediction).where(
                    RacePrediction.race_id.in_(race_ids),
                    RacePrediction.analysis_mode == "auto_daily",
                    RacePrediction.user_id.is_(None),
                )
            )).scalars().all()
        }

        winners: dict[str, str] = {}
        for meet_id in {rid.rsplit("-", 1)[0] for rid in race_ids if "-" in rid}:
            try:
                meet = await get_na_meet_results(meet_id)
            except Exception:
                continue
            for race in meet.get("races", []):
                number = str((race.get("race_key") or {}).get("race_number", ""))
                runners = race.get("runners") or []
                if number and runners:
                    winners[f"{meet_id}-{number}"] = runners[0].get("horse_name") or ""

        settled = 0
        for pick in pending:
            winner = winners.get(pick.race_id)
            if not winner:
                continue
            graded = score_pick(
                pick.horse_key,
                horse_key(winner),
                horse_key(secretariat[pick.race_id]) if secretariat.get(pick.race_id) else None,
            )
            pick.winner_name = winner[:160]
            pick.correct = graded["correct"]
            pick.secretariat_correct = graded["secretariat_correct"]
            pick.beat_secretariat = graded["beat_secretariat"]
            pick.points = graded["points"]
            pick.settled = True
            settled += 1
        await db.commit()
    return settled
