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

# The stake every contest bet is scored at: the US track minimum, and the base
# US win/place/show payoffs are quoted at.
STAKE = 2.0

# Bet types a player can call, and what each one is worth.
#
#   picks     how many horses the bet needs, in order
#   depth     how deep in the finish the selection has to land (win=1, show=3)
#   points    scaled against how often the bet actually lands, so an easy bet
#             can't out-earn a hard one. Anchored to Secretariat's own measured
#             hit rates over 7,595 settled races: win 24%, place 44%, show 58%.
#             Win stays 10 so every pick scored before bet types existed keeps
#             the value it was awarded.
BET_TYPES: dict[str, dict] = {
    "show":     {"picks": 1, "depth": 3, "points": 5,  "label": "Show"},
    "place":    {"picks": 1, "depth": 2, "points": 7,  "label": "Place"},
    "win":      {"picks": 1, "depth": 1, "points": 10, "label": "Win"},
    "exacta":   {"picks": 2, "depth": 2, "points": 25, "label": "Exacta"},
    "trifecta": {"picks": 3, "depth": 3, "points": 50, "label": "Trifecta"},
}
DEFAULT_BET_TYPE = "win"

# A pick the official chart still can't settle after this long is voided: it
# scores nothing and counts nowhere, rather than being graded a loss we can't
# demonstrate or re-fetched forever.
UNSETTLEABLE_AFTER_DAYS = 2


def bet_spec(bet_type: str) -> dict:
    """The rules for a bet type, falling back to win for unknown/legacy rows."""
    return BET_TYPES.get(bet_type or DEFAULT_BET_TYPE, BET_TYPES[DEFAULT_BET_TYPE])


def bet_hit(bet_type: str, pick_keys: list, finish_keys: list) -> Optional[bool]:
    """Did this bet land, given the official finish order (top 3)?

    `finish_keys` is the chart's finish order as horse keys. Returns None when
    the chart is too short to settle the bet — an exacta can't be graded off a
    chart that only names the winner — rather than scoring it as a loss.
    """
    spec = bet_spec(bet_type)
    n, depth = spec["picks"], spec["depth"]
    if len(pick_keys) < n or not all(pick_keys[:n]):
        return None
    if len(finish_keys) < depth:
        return None
    if n == 1:
        # Straight bet: the horse has to finish within `depth`.
        return pick_keys[0] in finish_keys[:depth]
    # Exotic: exact order, no boxes.
    return pick_keys[:n] == finish_keys[:n]


def score_pick(pick_key: str, winner_key: str, secretariat_key: Optional[str],
               bet_type: str = DEFAULT_BET_TYPE, hit: Optional[bool] = None) -> dict:
    """Grade one pick against the official winner and Secretariat's call.

    `hit` is whether the bet as placed landed; when omitted it falls back to
    "your first selection won", which is what a win bet means and what every
    pick made before bet types existed was graded on.
    """
    correct = bet_hit(bet_type, [pick_key], [winner_key]) if hit is None else hit
    correct = bool(correct)
    secretariat_correct = (
        None if not secretariat_key else secretariat_key == winner_key
    )
    beat = bool(correct and secretariat_correct is False)
    points = (bet_spec(bet_type)["points"] if correct else 0) + (POINTS_BEAT_BONUS if beat else 0)
    return {
        "correct": correct,
        "secretariat_correct": secretariat_correct,
        "beat_secretariat": beat,
        "points": points,
    }


def bet_payoff(bet_type: str, pick_keys: list, race_result: dict) -> Optional[float]:
    """What a $2 bet returned, straight from the official chart. None = unpriced.

    Returns the gross return per $2 (US payoffs include the stake, so a $2 win
    bet "paying $6.40" hands back $6.40). A losing bet returns 0.0. None means
    the chart carries no price for that pool, so the bet can't be settled either
    way — never a loss by default.
    """
    from app.services.horse_form import horse_key
    from app.services.ticket import per_stake

    runners = (race_result or {}).get("runners") or []
    if not runners:
        return None
    spec = bet_spec(bet_type)
    finish = [horse_key(r.get("horse_name") or r.get("horse") or "") for r in runners]
    hit = bet_hit(bet_type, pick_keys, finish)
    if hit is None:
        return None

    if spec["picks"] == 1:
        field = {"win": "win_payoff", "place": "place_payoff", "show": "show_payoff"}[bet_type]
        # The winner collects from every pool that ran, so its own payoffs are
        # what reveal whether this pool existed at all. Small fields often have
        # no show pool, and a missing pool is not a losing bet.
        try:
            if float(runners[0].get(field) or 0) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        if not hit:
            return 0.0
        row = next((r for r in runners
                    if horse_key(r.get("horse_name") or r.get("horse") or "") == pick_keys[0]), None)
        try:
            return round(float((row or {}).get(field) or 0), 2)
        except (TypeError, ValueError):
            return None

    code = {"exacta": "E", "trifecta": "T"}[bet_type]
    pool = next((p for p in (race_result.get("payoffs") or []) if p.get("wager_type") == code), None)
    if not pool:
        return None  # this race didn't offer the pool, or the chart lacks it
    if not hit:
        return 0.0
    return per_stake(pool.get("payoff_amount"), pool.get("base_amount"), STAKE)


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
    lose to it. A voided pick (correct is None, no official price) is skipped
    entirely: it isn't a loss, so it can't break a run.
    """
    streak = 0
    for pick in reversed(list(settled_in_order)):
        if pick.get("correct") is None:
            continue  # voided: no result either way, so it can't end a streak
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


async def settle_pending_picks(user_id: Optional[int] = None) -> int:
    """Grade every unsettled pick whose race has an official result. Idempotent.

    With `user_id`, grades only that player's picks — cheap enough to run when
    they open their calls, so a race that just went official doesn't read as
    "waiting on the result" for up to the scheduler's ten minutes. Meet results
    are cached, so the common case costs no API call at all.

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
        where = [
            ContestPick.settled == False,  # noqa: E712
            ContestPick.race_date <= date.today(),
        ]
        if user_id is not None:
            where.append(ContestPick.user_id == user_id)
        pending = list((await db.execute(select(ContestPick).where(*where))).scalars().all())
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

        # Keep the whole race, not just the winner's name: exotics need the
        # finish order and the payoff pools to be graded and priced.
        results: dict[str, dict] = {}
        for meet_id in {rid.rsplit("-", 1)[0] for rid in race_ids if "-" in rid}:
            try:
                meet = await get_na_meet_results(meet_id)
            except Exception:
                continue
            for race in meet.get("races", []):
                number = str((race.get("race_key") or {}).get("race_number", ""))
                if number and (race.get("runners") or []):
                    results[f"{meet_id}-{number}"] = race

        settled = 0
        stale_before = date.today() - timedelta(days=UNSETTLEABLE_AFTER_DAYS)
        for pick in pending:
            race = results.get(pick.race_id)
            if not race:
                # The chart never arrived. Old meets 404 outright, so without a
                # cutoff these picks are re-fetched on every pass forever and
                # sit "waiting on the result" for good.
                if pick.race_date < stale_before:
                    pick.correct = None
                    pick.points = 0
                    pick.payoff = None
                    pick.settled = True
                    settled += 1
                continue
            runners = race.get("runners") or []
            winner = runners[0].get("horse_name") or ""
            if not winner:
                continue
            finish = [horse_key(r.get("horse_name") or "") for r in runners]
            keys = [s.get("key") for s in (pick.selections or [])] or [pick.horse_key]
            bet_type = pick.bet_type or DEFAULT_BET_TYPE

            hit = bet_hit(bet_type, keys, finish)
            if hit is None:
                # Chart too short to settle this bet (a 2-finisher chart can't
                # grade a trifecta). Give the chart two days to fill in, then
                # void the pick rather than re-fetching the meet forever or
                # scoring a loss we can't actually demonstrate.
                if pick.race_date < stale_before:
                    pick.winner_name = winner[:160]
                    pick.correct = None
                    pick.points = 0
                    pick.payoff = None
                    pick.settled = True
                    settled += 1
                continue
            graded = score_pick(
                pick.horse_key, horse_key(winner),
                horse_key(secretariat[pick.race_id]) if secretariat.get(pick.race_id) else None,
                bet_type=bet_type, hit=hit,
            )
            pick.winner_name = winner[:160]
            pick.correct = graded["correct"]
            pick.secretariat_correct = graded["secretariat_correct"]
            pick.beat_secretariat = graded["beat_secretariat"]
            pick.points = graded["points"]
            pick.payoff = bet_payoff(bet_type, keys, race)
            pick.settled = True
            settled += 1
        await db.commit()
    return settled
