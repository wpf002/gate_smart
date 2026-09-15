#!/usr/bin/env python3
"""
prompt_report.py — Does the honest prompt pick better than the legacy one?

The legacy system prompt tells Secretariat to lead with speed figures, running
styles, workouts and trainer percentages that never reach it for races since
2024. The honest arm describes the data it actually gets. Races split 50/50 by
hash (see prompt_arm_for_race), so both arms face the same days and tracks.

Win rate alone can mislead. An arm that sides with the favorite more often wins
more races without handicapping any better (the lean pick-depth arm did exactly
that), so this also prints each arm's favorite rate and its win rate on each
side of that choice, plus flat $2 win ROI.

Usage:
    cd backend
    python scripts/prompt_report.py
    python scripts/prompt_report.py --since 2026-09-16
"""
import argparse
import asyncio
import datetime
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Below this many settled races per arm, only a very large gap is readable.
READABLE_PER_ARM = 700


def wilson(w: int, n: int) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    z, p = 1.96, w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def detectable_gap(p: float, n1: int, n2: int) -> float | None:
    """Smallest win-rate gap (points) that would reach p<0.05 at these sizes."""
    if not n1 or not n2:
        return None
    return 100.0 * 1.96 * math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))


async def main(since: datetime.date) -> None:
    from sqlalchemy import text as T

    from app.core import database as _db
    from app.services.secretariat import PROMPT_ARM_HONEST, PROMPT_ARM_LEGACY, PROMPT_HONEST_PERCENT
    from scripts.score_lessons import two_proportion_p

    await _db.init_db()
    base = ("result_fetched AND analysis_mode = 'auto_daily' AND user_id IS NULL "
            "AND lock_source = 'nightly' AND prompt_arm IS NOT NULL AND race_date >= :since")
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(T(f"""
            SELECT prompt_arm, COUNT(*) n,
                   SUM(CASE WHEN top_pick_correct THEN 1 ELSE 0 END) w,
                   SUM(CASE WHEN in_the_money THEN 1 ELSE 0 END) itm,
                   COUNT(*) FILTER (WHERE top_pick_is_favorite) fav_n,
                   SUM(CASE WHEN top_pick_is_favorite AND top_pick_correct THEN 1 ELSE 0 END) fav_w,
                   COUNT(*) FILTER (WHERE top_pick_is_favorite IS FALSE) fade_n,
                   SUM(CASE WHEN top_pick_is_favorite IS FALSE AND top_pick_correct THEN 1 ELSE 0 END) fade_w,
                   COUNT(top_pick_win_payoff) priced,
                   SUM(COALESCE(top_pick_win_payoff, 0)) returned,
                   COUNT(DISTINCT race_date) days
            FROM race_predictions WHERE {base}
            GROUP BY 1 ORDER BY 1
        """), {"since": since})).all()
        reasons = (await db.execute(T(f"""
            SELECT prompt_arm, fade_reason, COUNT(*) n,
                   SUM(CASE WHEN top_pick_correct THEN 1 ELSE 0 END) w
            FROM race_predictions WHERE {base} AND top_pick_is_favorite IS FALSE
            GROUP BY 1, 2 ORDER BY 1, 3 DESC
        """), {"since": since})).all()

    print("=" * 78)
    print(f"PROMPT TEST — honest vs legacy system prompt, settled nightly picks since {since}")
    print(f"PROMPT_HONEST_PERCENT = {PROMPT_HONEST_PERCENT}")
    print("=" * 78)
    if not rows:
        print("\nNo settled races carry a prompt arm yet.")
        print("Picks get an arm from the next nightly slate; results settle the morning after.")
        return

    stats = {r[0]: r for r in rows}
    print(f"\n{'arm':<9}{'races':>7}{'win':>8}{'95% CI':>16}{'ITM':>8}{'$2 ROI':>9}"
          f"{'picks fav':>11}{'fav wins':>10}{'fade wins':>11}")
    for arm in (PROMPT_ARM_LEGACY, PROMPT_ARM_HONEST):
        if arm not in stats:
            continue
        _, n, w, itm, fav_n, fav_w, fade_n, fade_w, priced, returned, _days = stats[arm]
        lo, hi = wilson(w, n)
        roi = (returned - 2 * priced) / (2 * priced) if priced else None
        print(f"{arm:<9}{n:>7}{w/n:>7.1%}{f'[{lo:.0%}–{hi:.0%}]':>16}{itm/n:>7.1%}"
              f"{(f'{roi:>+8.0%}' if roi is not None else '       —'):>9}"
              f"{fav_n/n:>10.0%}{(f'{fav_w/fav_n:.1%}' if fav_n else '—'):>10}"
              f"{(f'{fade_w/fade_n:.1%}' if fade_n else '—'):>11}")

    if PROMPT_ARM_LEGACY in stats and PROMPT_ARM_HONEST in stats:
        L, H = stats[PROMPT_ARM_LEGACY], stats[PROMPT_ARM_HONEST]
        diff = 100.0 * (H[2] / H[1] - L[2] / L[1])
        p = two_proportion_p(H[2], H[1], L[2], L[1])
        pooled = (H[2] + L[2]) / (H[1] + L[1])
        gap = detectable_gap(pooled, H[1], L[1])
        print(f"\nhonest minus legacy: {diff:+.1f} win points" + (f", p={p:.3f}" if p is not None else ""))
        if gap is not None:
            print(f"At these sample sizes a gap needs to be about {gap:.1f} points to reach p<0.05.")
        if min(H[1], L[1]) < READABLE_PER_ARM:
            print(f"Too early to call: want {READABLE_PER_ARM}+ settled races per arm "
                  f"(about two weeks of slates).")
        elif p is not None and p < 0.05:
            better = "honest" if diff > 0 else "legacy"
            print(f"Significant: the {better} prompt wins more often.")
            print("Check the favorite columns before shipping: if the gap comes only from")
            print("picking more favorites while each side's win rate is flat, the prompt")
            print("changed how often it sides with the market, not how well it handicaps.")
        else:
            print("No significant difference yet.")

    if reasons:
        print("\nFade reasons (non-favorite picks):")
        for arm in (PROMPT_ARM_LEGACY, PROMPT_ARM_HONEST):
            arm_rows = [r for r in reasons if r[0] == arm]
            if not arm_rows:
                continue
            total = sum(r[2] for r in arm_rows)
            parts = [f"{r[1] or 'not_recorded'} {r[2]} ({r[3]/r[2]:.0%} won)" for r in arm_rows[:6]]
            print(f"  {arm} ({total} fades): " + ", ".join(parts))


if __name__ == "__main__":
    from app.services.secretariat import PROMPT_TEST_START

    ap = argparse.ArgumentParser(description="Compare pick accuracy by system prompt")
    ap.add_argument("--since", type=datetime.date.fromisoformat,
                    default=datetime.date.fromisoformat(PROMPT_TEST_START))
    asyncio.run(main(ap.parse_args().since))
