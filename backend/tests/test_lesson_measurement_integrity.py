"""
The measurement has to be able to be wrong.

An audit of the loop found the scoring apparatus could manufacture confident
verdicts from nothing. These are the three defects that mattered most, each
pinned so it cannot come back:

1. The control group had only a lower date bound. A lesson's treated count
   freezes the night it drops out of the injected set, but its control kept
   absorbing races for the life of the table — so one good day got scored
   against a month of baseline and returned PROVEN.
2. A FAILING lesson was resurrected by the next reflect run, because its text
   stayed in the calibration list that feeds the curator. Reactivation reset
   activated_at, discarding the very races that condemned it, and the next
   scoring pass overwrote FAILING with PENDING. The cycle never ended.
3. Lean-arm and fallback picks were stamped with lesson_ids although their
   prompt carried no lessons at all — filing ~20% of the slate as evidence for
   lessons it never saw.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SCORE = (BACKEND / "scripts" / "score_lessons.py").read_text()
STORE = (BACKEND / "app" / "services" / "lesson_store.py").read_text()
NIGHTLY = (BACKEND / "scripts" / "nightly_predict_all.py").read_text()
MEMORY = (BACKEND / "app" / "services" / "lesson_memory.py").read_text()


def test_both_groups_are_restricted_to_days_the_lesson_was_carried():
    assert "injected_dates" in SCORE
    assert "if race_date not in injected_dates:" in SCORE
    # The old lower-bound-only filter must be gone.
    assert "race_date < activated.date()" not in SCORE


def test_a_failed_lesson_is_evicted_from_the_curators_candidate_pool():
    assert "failed_texts" in SCORE
    assert "cal.lessons" in SCORE, "score_lessons must prune the calibration list"


def test_a_failing_lesson_cannot_be_resurrected():
    block = STORE[STORE.index('if row.status != "active":'):]
    assert 'row.verdict == "FAILING"' in block
    # The FAILING branch must skip the row entirely rather than fall through
    # into reactivation.
    after_failing = block[block.index('row.verdict == "FAILING"'):]
    assert "continue" in after_failing[:1200]
    assert after_failing.index("continue") < after_failing.index("row.status = \"active\"")


def test_reactivation_resets_the_evidence_it_claims_to_reset():
    """The branch's comment promised a restarted record while leaving verdict,
    lift and scope_races intact — so stale numbers rode into a new lifetime."""
    block = STORE[STORE.index("row.activated_at = now"):]
    for field in ("row.scope_races", "row.baseline_races", "row.lift", "row.verdict"):
        assert field in block[:700], f"{field} not reset on reactivation"


def test_only_lesson_bearing_picks_record_provenance():
    guard = re.search(r'if lock_source == "nightly":\s*\n\s*try:\s*\n\s*from app\.services\.lesson_memory import lessons_for_race',
                      NIGHTLY)
    assert guard, "lesson provenance must be guarded on the full-analysis path"
    # Defaults must be set before the guard so lean/fallback rows write NULL.
    assert "lesson_arm, lesson_ids = None, None\n            if lock_source" in NIGHTLY


def test_the_playbook_is_pinned_for_the_length_of_a_run():
    """Prompts are built now and rows written up to 45 minutes later, with
    score_lessons rewriting the ranking fields in between."""
    assert "def freeze_lessons" in MEMORY
    assert "_frozen" in MEMORY
    assert "freeze_lessons(True)" in NIGHTLY


def test_the_activation_day_is_excluded_from_evidence():
    """Two predict passes run for the same race_date (12:00 UTC, then 15:00
    --only-missing) with reflect minting lessons at 14:30 between them. On a
    lesson's first day, treated is whatever the second pass covered and control
    whatever the first did — split by feed timing and which tracks posted late,
    not by the race_id hash. That day cannot be counted as contemporaneous."""
    assert "injected_dates.discard(lesson.activated_at.date())" in SCORE


def test_the_eviction_count_is_computed_before_the_assignment():
    """`cal.lessons = kept` first, then `len(cal.lessons) - len(kept)` is always
    zero — the log claimed nothing was pruned every time it pruned something."""
    block = SCORE[SCORE.index("kept = [l for l in cal.lessons"):]
    assert "removed = len(cal.lessons) - len(kept)" in block[:300]
    assert block.index("removed =") < block.index("cal.lessons = kept")
