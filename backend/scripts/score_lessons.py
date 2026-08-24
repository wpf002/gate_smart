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
Every pick records which lessons its prompt carried (race_predictions.lesson_ids)
and which A/B arm it was in. So for one lesson we can compare, over the SAME
days and only within the races that lesson claims to govern:

    treated — in-scope races whose prompt carried this lesson
    control — in-scope races over the same period that did not

That is a contemporaneous comparison, not a before/after one, so it is not
confounded by seasonal form, track mix, or any other change shipped in the
meantime. Arm assignment is a deterministic hash of race_id, independent of
track, date and field size, so neither group gets the easier races.

A lesson sitting in the top slots of BOTH arms has no control group and stays
PENDING. That is honest: we cannot measure a lesson we never withheld.

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


async def main(dry_run: bool) -> None:
    from sqlalchemy import select, text as T

    from app.core import database as _db
    from app.models.lesson import SecretariatLesson
    from app.services.lesson_scope import describe_scope, race_matches_scope

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

    # One pass over the evidence, reused for every lesson. Only races that went
    # through the provenance-recording path count: on older rows lesson_ids is
    # NULL, and absence there means "not recorded", not "not applied".
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(T("""
            SELECT race_type, surface, top_pick_correct, lesson_ids, race_date
            FROM race_predictions
            WHERE result_fetched AND analysis_mode = 'auto_daily' AND user_id IS NULL
              AND lesson_ids IS NOT NULL
        """))).all()

    print(f"[score_lessons] {len(lessons)} lessons | {len(rows)} scored races with provenance")
    if not rows:
        print("  No races carry lesson provenance yet. Verdicts stay PENDING until")
        print("  the next nightly slate runs with the playbook wired in.")
        return

    now = datetime.now(timezone.utc)
    changed = []

    for lesson in lessons:
        scope = lesson.scope or {}
        activated = lesson.activated_at
        t_n = t_w = c_n = c_w = 0

        for race_type, surface, correct, lesson_ids, race_date in rows:
            if activated and race_date and race_date < activated.date():
                continue
            if not race_matches_scope(race_type, surface, scope):
                continue
            if lesson.id in (lesson_ids or []):
                t_n += 1
                t_w += bool(correct)
            else:
                c_n += 1
                c_w += bool(correct)

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
                    f"measured {lift:+.1f} pts vs control over {t_n} in-scope races (p={p:.3f})"
                )

        tag = f"{was}->{verdict}" if was != verdict else verdict
        detail = (f"treated {t_w}/{t_n} vs control {c_w}/{c_n}"
                  + (f" | {lift:+.1f} pts p={p:.3f}" if lift is not None and p is not None else ""))
        print(f"  [{tag:<18}] {detail:<58} {describe_scope(scope)}")
        print(f"      {lesson.text[:120]}")
        if was != verdict:
            changed.append((lesson.text[:60], was, verdict))

    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            for lesson in lessons:
                await db.merge(lesson)
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
