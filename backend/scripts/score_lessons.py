#!/usr/bin/env python3
"""
score_lessons.py — Measure whether each lesson actually helps, and retire the
ones that don't.

This is the part the learning loop was missing. Lessons were synthesised nightly
and curated by asking a model which ones read best, but nothing ever checked
whether a lesson changed results. Nineteen weeks and 13,677 races produced no
measurable improvement, because nothing in the loop selected for what was true.

How a lesson is scored
----------------------
In the measured arm every eligible lesson gets its own coin flip per race: it is
either carried by that race's prompt or withheld from it. Both outcomes are
recorded (race_predictions.lesson_ids and lesson_holdout_ids). So for one lesson,
within the races it claims to govern:

    treated — races whose prompt carried it
    control — races that were eligible for it and withheld it

The two groups come from the same arm, the same days and the same predict passes,
split only by a hash of (race_id, lesson id). No date windows are needed to make
that contemporaneous, and a lesson's verdict no longer depends on which other
lessons it happened to ride alongside.

Before per-lesson holdouts every measured race carried the same top lessons, so
"carried lesson X" meant "was in the measured arm". Each lesson's record was the
arm difference counted again under its name; two lessons showed identical
numbers. Rows from that period have no holdout list and are not used here. The
arm-level A/B in scripts/lesson_report.py still reads them.

Usage:
    cd backend
    python scripts/score_lessons.py
    python scripts/score_lessons.py --dry-run
"""
import argparse
import asyncio
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# A lesson needs a real body of evidence before we claim anything about it.
MIN_TREATED = int(os.getenv("LESSON_MIN_TREATED", "80"))
# Two-sided significance for calling a lesson PROVEN or FAILING. Kept at 0.05
# rather than a looser bar because a dozen lessons are tested each night and
# some will look good by chance; see the multiplicity note in the report.
ALPHA = float(os.getenv("LESSON_ALPHA", "0.05"))


def two_proportion_p(w1: int, n1: int, w2: int, n2: int) -> float | None:
    """Two-sided p-value for a difference in win rates."""
    if not n1 or not n2:
        return None
    p1, p2 = w1 / n1, w2 / n2
    pooled = (w1 + w2) / (n1 + n2)
    if pooled in (0.0, 1.0):
        return None
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    return math.erfc(abs((p1 - p2) / se) / math.sqrt(2))


def classify(treated_w, treated_n, control_w, control_n) -> tuple[str, float | None, float | None]:
    """(verdict, lift in percentage points, p-value)."""
    if treated_n < MIN_TREATED or control_n < MIN_TREATED:
        return "PENDING", None, None
    lift = 100.0 * (treated_w / treated_n - control_w / control_n)
    p = two_proportion_p(treated_w, treated_n, control_w, control_n)
    if p is not None and p < ALPHA:
        return ("PROVEN" if lift > 0 else "FAILING"), lift, p
    return "UNPROVEN", lift, p


def count_evidence(rows, lesson_id, scope) -> tuple[int, int, int, int]:
    """(treated wins, treated races, control wins, control races) for one lesson.

    `rows` are (race_type, surface, won, lesson_ids, lesson_holdout_ids). Pure, so
    the rule that defines a control group is testable without a database.

    A row counts only if it is under per-lesson randomization (its holdout list is
    an array) and in the lesson's scope. It is treated if it carried the lesson,
    control if it withheld it, and ignored if the lesson was not eligible that day.
    """
    from app.services.lesson_scope import race_matches_scope

    t_w = t_n = c_w = c_n = 0
    for race_type, surface, won, carried, withheld in rows:
        if not isinstance(withheld, list) or not race_matches_scope(race_type, surface, scope):
            continue
        if lesson_id in (carried or []):
            t_n += 1
            t_w += bool(won)
        elif lesson_id in withheld:
            c_n += 1
            c_w += bool(won)
    return t_w, t_n, c_w, c_n


async def main(dry_run: bool) -> None:
    from sqlalchemy import select, text as T

    from app.core import database as _db
    from app.models.lesson import SecretariatLesson
    from app.services.lesson_scope import describe_scope

    await _db.init_db()

    async with _db._AsyncSessionLocal() as db:
        lessons = list((await db.execute(select(SecretariatLesson))).scalars().all())

    # First run after deploy: adopt the lessons already in the calibration row so
    # the playbook starts from what Secretariat currently believes rather than
    # from nothing. Reflect keeps the two in sync from here on.
    if not lessons and not dry_run:
        from app.models.accuracy import SecretariatCalibration
        from app.services.lesson_store import sync_lessons
        async with _db._AsyncSessionLocal() as db:
            cal = await db.get(SecretariatCalibration, 1)
            legacy = list(cal.lessons or []) if cal else []
        if legacy:
            summary = await sync_lessons(legacy)
            print(f"[score_lessons] seeded playbook from calibration: {summary['new']} lessons")
            async with _db._AsyncSessionLocal() as db:
                lessons = list((await db.execute(select(SecretariatLesson))).scalars().all())

    if not lessons:
        print("[score_lessons] no lessons recorded yet — nothing to score")
        return

    # One pass over the evidence, reused for every lesson. Only races under
    # per-lesson randomization count, and those are exactly the rows with a
    # holdout array (an empty array still counts: that race withheld nothing).
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(T("""
            SELECT race_type, surface, top_pick_correct, lesson_ids, lesson_holdout_ids
            FROM race_predictions
            WHERE result_fetched AND analysis_mode = 'auto_daily' AND user_id IS NULL
              -- jsonb null is NOT sql NULL: a row written with a JSON `null`
              -- passes `IS NOT NULL` and decodes to None.
              AND lesson_ids IS NOT NULL AND jsonb_typeof(lesson_ids) = 'array'
              AND lesson_holdout_ids IS NOT NULL AND jsonb_typeof(lesson_holdout_ids) = 'array'
        """))).all()

    print(f"[score_lessons] {len(lessons)} lessons | {len(rows)} settled races under per-lesson holdouts")
    if not rows:
        print("  No settled races under per-lesson holdouts yet. Verdicts stay PENDING")
        print("  until the first randomized slate has results.")

    now = datetime.now(timezone.utc)
    changed = []
    failed_texts: list[str] = []

    for lesson in lessons:
        scope = lesson.scope or {}
        t_w, t_n, c_w, c_n = count_evidence(rows, lesson.id, scope)

        verdict, lift, p = classify(t_w, t_n, c_w, c_n)
        was = lesson.verdict

        if not dry_run:
            lesson.scope_races, lesson.scope_wins = t_n, t_w
            lesson.baseline_races, lesson.baseline_wins = c_n, c_w
            lesson.lift, lesson.p_value = lift, p
            lesson.verdict, lesson.measured_at = verdict, now
            if t_n:
                lesson.was_injected = True
            # A lesson measurably worse than its own control is worse than no
            # lesson. Retire it — but keep the row, because the record of what
            # failed is the most useful thing in the playbook.
            if verdict == "FAILING" and lesson.status == "active":
                lesson.status = "retired"
                lesson.retired_at = now
                lesson.retire_reason = (
                    f"measured {lift:+.1f} pts vs withheld over {t_n} in-scope races (p={p:.3f})"
                )
                # Also evict it from the calibration list, which is the curator's
                # candidate pool. Leaving it there let the next reflect run hand
                # the same text straight back, reactivating the lesson and
                # resetting the very evidence that condemned it.
                failed_texts.append(lesson.text)

        tag = f"{was}->{verdict}" if was != verdict else verdict
        detail = (f"carried {t_w}/{t_n} vs withheld {c_w}/{c_n}"
                  + (f" | {lift:+.1f} pts p={p:.3f}" if lift is not None and p is not None else ""))
        print(f"  [{tag:<18}] {detail:<58} {describe_scope(scope)}")
        print(f"      {lesson.text[:120]}")
        if was != verdict:
            changed.append((lesson.text[:60], was, verdict))

    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            for lesson in lessons:
                await db.merge(lesson)
            if failed_texts:
                from app.models.accuracy import SecretariatCalibration
                cal = await db.get(SecretariatCalibration, 1)
                if cal and cal.lessons:
                    kept = [l for l in cal.lessons if l not in failed_texts]
                    removed = len(cal.lessons) - len(kept)
                    if removed:
                        cal.lessons = kept
                        print(f"  evicted {removed} failed lesson(s) from the "
                              f"curator's candidate pool")
            await db.commit()
        from app.services.lesson_memory import _invalidate_cache
        _invalidate_cache()

    print(f"\n{'Would update' if dry_run else 'Updated'} {len(lessons)} lessons; "
          f"{len(changed)} changed verdict.")
    if len(lessons) > 1:
        print(f"Note: {len(lessons)} lessons tested at alpha={ALPHA}. With this many "
              f"comparisons roughly {len(lessons)*ALPHA:.1f} could reach significance by "
              f"chance, so a single PROVEN verdict is a signal to watch, not proof on its own. "
              f"The arm-level A/B in scripts/ab_report.py is the aggregate test.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Measure and retire Secretariat's lessons")
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main(ap.parse_args().dry_run))
