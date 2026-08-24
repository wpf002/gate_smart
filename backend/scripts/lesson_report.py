#!/usr/bin/env python3
"""
lesson_report.py — What Secretariat has actually learned.

Two questions, answered from results rather than narrative:

  1. Per lesson: does it beat contemporaneous races in its own scope that did
     not carry it?
  2. Overall: does the evidence-ranked playbook beat the old five-slot recency
     window? That arm-level A/B is the causal test, and the one that decides
     whether the new loop stays.

Usage:
    cd backend
    python scripts/lesson_report.py
    python scripts/lesson_report.py --days 30
"""
import argparse
import asyncio
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def wilson(w: int, n: int) -> tuple[float, float]:
    """95% Wilson interval — honest about small samples where normal-approx is not."""
    if not n:
        return (0.0, 0.0)
    z, p = 1.96, w / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


async def main(days: int) -> None:
    from sqlalchemy import select, text as T

    from app.core import database as _db
    from app.models.lesson import SecretariatLesson
    from app.services.lesson_scope import describe_scope
    from scripts.score_lessons import two_proportion_p

    await _db.init_db()

    async with _db._AsyncSessionLocal() as db:
        lessons = list((await db.execute(
            select(SecretariatLesson).order_by(SecretariatLesson.id)
        )).scalars().all())

    print("=" * 78)
    print("SECRETARIAT PLAYBOOK")
    print("=" * 78)
    if not lessons:
        print("No lessons recorded yet. The next nightly reflect populates this.")
        return

    order = {"PROVEN": 0, "UNPROVEN": 1, "PENDING": 2, "FAILING": 3}
    for lesson in sorted(lessons, key=lambda l: (l.status != "active",
                                                 order.get(l.verdict, 4), -l.id)):
        state = lesson.verdict if lesson.status == "active" else f"RETIRED/{lesson.verdict}"
        print(f"\n[{state}] #{lesson.id}  {lesson.lesson_type.upper()}  "
              f"scope: {describe_scope(lesson.scope or {})}")
        print(f"  {lesson.text[:150]}")
        if lesson.scope_races or lesson.baseline_races:
            lo, hi = wilson(lesson.scope_wins, lesson.scope_races)
            t = f"{lesson.scope_wins}/{lesson.scope_races}"
            c = f"{lesson.baseline_wins}/{lesson.baseline_races}"
            tr = lesson.win_rate()
            cr = lesson.baseline_rate()
            print(f"  carried {t} ({tr:.1%} [{lo:.1%}–{hi:.1%}])  vs  without {c}"
                  + (f" ({cr:.1%})" if cr is not None else ""))
            if lesson.lift is not None and lesson.p_value is not None:
                print(f"  lift {lesson.lift:+.1f} pts, p={lesson.p_value:.3f}")
        else:
            print("  no in-scope races with provenance yet")
        if lesson.retire_reason:
            print(f"  retired: {lesson.retire_reason}")

    # ── The causal test ─────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"A/B: evidence-ranked playbook vs the old recency window (last {days} days)")
    print("=" * 78)
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(T(f"""
            SELECT lesson_arm, COUNT(*) n,
                   SUM(CASE WHEN top_pick_correct THEN 1 ELSE 0 END) w,
                   SUM(CASE WHEN in_the_money THEN 1 ELSE 0 END) itm
            FROM race_predictions
            WHERE result_fetched AND analysis_mode = 'auto_daily' AND user_id IS NULL
              AND lesson_arm IS NOT NULL
              AND race_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
            GROUP BY lesson_arm ORDER BY lesson_arm
        """))).all()

    if not rows:
        print("No settled races carry an arm yet.")
        print("Picks get an arm from the next nightly slate; results settle the morning after.")
        return

    stats = {}
    print(f"\n{'arm':<12}{'races':>8}{'win':>9}{'95% CI':>18}{'ITM':>9}")
    for arm, n, w, itm in rows:
        lo, hi = wilson(w, n)
        stats[arm] = (w, n)
        print(f"{arm:<12}{n:>8}{w/n:>8.1%}{f'[{lo:.1%}–{hi:.1%}]':>18}{itm/n:>8.1%}")

    if len(stats) == 2 and "measured" in stats and "recency" in stats:
        (mw, mn), (rw, rn) = stats["measured"], stats["recency"]
        p = two_proportion_p(mw, mn, rw, rn)
        diff = 100.0 * (mw / mn - rw / rn)
        print(f"\ndifference: {diff:+.1f} points" + (f", p={p:.3f}" if p is not None else ""))
        if min(mn, rn) < 400:
            need = 400 - min(mn, rn)
            print(f"Too early to call — roughly {need} more settled races per arm before "
                  f"a difference this size would be readable.")
        elif p is not None and p < 0.05:
            better = "evidence-ranked playbook" if diff > 0 else "old recency window"
            print(f"Significant: the {better} is ahead.")
        else:
            print("No significant difference yet. Keep both arms running.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Secretariat playbook + lesson A/B report")
    ap.add_argument("--days", type=int, default=30)
    asyncio.run(main(ap.parse_args().days))
