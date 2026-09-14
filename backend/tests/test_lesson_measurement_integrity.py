"""
The measurement has to be able to be wrong.

An audit of the loop found the scoring apparatus could manufacture confident
verdicts from nothing. These are the three defects that mattered most, each
pinned so it cannot come back:

1. The control group was not a control. It first had only a lower date bound,
   so one good day got scored against a month of baseline and returned PROVEN.
   Then, with every measured race carrying the same top lessons, "did not carry
   lesson X" meant "was in the other arm", and each lesson's record was the arm
   difference counted again. Control is now the races that withheld the lesson
   by per-race coin flip.
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


def test_control_is_the_races_that_withheld_the_lesson():
    """The control group used to be every in-scope race that did not carry the
    lesson. Every measured race carried the same top lessons, so that was just
    the other arm, and two different lessons showed identical records. Control is
    now only races that were eligible for the lesson and withheld it."""
    from scripts.score_lessons import count_evidence

    rows = [
        # race_type, surface, won, carried, withheld
        ("CLAIMING", "Dirt", True, [7, 9], [3]),    # carried 7
        ("CLAIMING", "Dirt", False, [9], [7, 3]),   # withheld 7
        ("CLAIMING", "Dirt", True, [9], [3]),       # 7 not eligible that race
        ("STAKES", "Turf", True, [7], []),          # carried 7, empty holdout list still counts
    ]
    assert count_evidence(rows, 7, {}) == (2, 2, 0, 1)


def test_rows_without_a_holdout_list_are_not_evidence():
    """Rows from before per-lesson holdouts (and recency-arm rows) have no holdout
    list. Counting them would bring the bundled comparison straight back."""
    from scripts.score_lessons import count_evidence

    rows = [
        ("CLAIMING", "Dirt", True, [7], None),
        ("CLAIMING", "Dirt", False, [], None),
    ]
    assert count_evidence(rows, 7, {}) == (0, 0, 0, 0)


def test_evidence_respects_the_lessons_scope():
    from scripts.score_lessons import count_evidence

    rows = [
        ("CLAIMING", "Turf", True, [7], []),
        ("CLAIMING", "Dirt", True, [7], []),
        ("STAKES", "Turf", False, [], [7]),
    ]
    turf_claiming = {"race_types": ["CLAIMING"], "surfaces": ["TURF"]}
    assert count_evidence(rows, 7, turf_claiming) == (1, 1, 0, 0)


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
    guard = re.search(r'if lock_source == "nightly":\s*\n\s*try:\s*\n\s*from app\.services\.lesson_memory import \(',
                      NIGHTLY)
    assert guard, "lesson provenance must be guarded on the full-analysis path"
    # Defaults must be set before the guard so lean/fallback rows write NULL.
    assert "lesson_arm, lesson_ids, lesson_holdout_ids = None, None, None\n            if lock_source" in NIGHTLY


def test_provenance_comes_from_the_same_assignment_as_the_prompt():
    """The prompt and the stored row must be built from one helper, or a lesson
    can be credited with races that never saw it."""
    assert "await lesson_assignment_for_race(race_id)" in NIGHTLY
    assert '"lesson_holdout_ids": lesson_holdout_ids' in NIGHTLY
    secretariat = (BACKEND / "app" / "services" / "secretariat.py").read_text()
    assert "await lesson_assignment_for_race(race_id)" in secretariat


def test_the_playbook_is_pinned_for_the_length_of_a_run():
    """Prompts are built now and rows written up to 45 minutes later, with
    score_lessons rewriting the ranking fields in between."""
    assert "def freeze_lessons" in MEMORY
    assert "_frozen" in MEMORY
    assert "freeze_lessons(True)" in NIGHTLY


def test_scoring_reads_only_randomized_rows():
    """Two predict passes per day with reflect minting lessons between them used
    to split a lesson's first day by pass, not by hash. Holdouts are decided per
    race inside whichever pass runs, so scoring needs no date windows, but it
    must only read rows that were randomized."""
    assert "jsonb_typeof(lesson_holdout_ids) = 'array'" in SCORE
    assert "injected_dates" not in SCORE


def test_the_eviction_count_is_computed_before_the_assignment():
    """`cal.lessons = kept` first, then `len(cal.lessons) - len(kept)` is always
    zero — the log claimed nothing was pruned every time it pruned something."""
    block = SCORE[SCORE.index("kept = [l for l in cal.lessons"):]
    assert "removed = len(cal.lessons) - len(kept)" in block[:300]
    assert block.index("removed =") < block.index("cal.lessons = kept")
