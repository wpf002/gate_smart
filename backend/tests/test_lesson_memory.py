"""
Secretariat's playbook: which lessons reach a pick, and on what basis.

The loop these tests protect exists because the old one did not work. Lessons
were injected as `cal.lessons[:5]` from a newest-first list, so memory was a
five-slot recency window — nine of fourteen curated lessons were stored, shown
in the nightly digest, and never read by any pick. Secretariat wrote in its own
digest that it kept reading a lesson in its notes and never applying it, which
was literally true. Over nineteen weeks and 13,677 races the win rate did not
move.

So: a lesson must be scoped (or it cannot be measured), ranked by measured record
(or recency decides), and the old behaviour must survive intact as the control
arm (or the A/B measures nothing).
"""
from datetime import datetime, timedelta, timezone

from app.services.lesson_memory import (
    ARM_MEASURED, ARM_RECENCY, LESSON_CONTROL_LIMIT,
    lesson_arm_for_race, render_lessons_block, select_lessons,
)
from app.services.lesson_scope import (
    canonical_race_type, describe_scope, parse_scope, race_matches_scope,
)

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


class L:
    """Minimal stand-in for SecretariatLesson so selection is testable without a DB."""

    def __init__(self, text, *, lesson_type="change", verdict="PENDING", lift=None,
                 age_days=0, status="active"):
        self.text = text
        self.lesson_type = lesson_type
        self.verdict = verdict
        self.lift = lift
        self.status = status
        self.created_at = NOW - timedelta(days=age_days)


# ── Scope: a lesson that cannot be scoped cannot be falsified ────────────────

def test_longest_race_type_phrase_wins():
    """"maiden claiming" must not also register as a bare "claiming" — the two
    are different populations and scoring the wrong one is worse than not
    scoring at all."""
    scope = parse_scope("When a maiden claiming race has a heavy chalk")
    assert scope["race_types"] == ["MAIDEN CLAIMING"]

    scope = parse_scope("In a claiming or maiden claiming race")
    assert set(scope["race_types"]) == {"CLAIMING", "MAIDEN CLAIMING"}

    scope = parse_scope("allowance optional claiming fields")
    assert scope["race_types"] == ["ALLOWANCE OPTIONAL CLAIMING"]


def test_surface_and_general_scopes():
    assert parse_scope("When handicapping turf races")["surfaces"] == ["TURF"]
    general = parse_scope("When I am uncertain about the winner, I build the exacta")
    assert general["race_types"] == [] and general["surfaces"] == []
    # An unscoped lesson governs every race rather than none.
    assert race_matches_scope("CLAIMING", "Dirt", general)


def test_price_band_is_parsed_but_never_matched():
    """A band like $2.40-$3.60 describes our own pick's odds. Selecting evidence
    by an attribute of the pick would condition the measurement on the very
    thing being measured, so it is recorded for display only."""
    scope = parse_scope("When the favorite is at $2.40–$3.60 I treat that as a red flag")
    assert scope["price_band"] == [2.40, 3.60]
    assert scope["race_types"] == [] and scope["surfaces"] == []
    assert race_matches_scope("STAKES", "Turf", scope)


def test_scope_matching_selects_the_right_races():
    scope = parse_scope("In claiming races on turf")
    assert race_matches_scope("CLAIMING", "Turf", scope)
    assert not race_matches_scope("CLAIMING", "Dirt", scope)
    assert not race_matches_scope("STAKES", "Turf", scope)


def test_composite_race_type_strings_still_resolve():
    """race_type also accepts composite strings; those must land in the same
    vocabulary instead of silently falling out of every scope."""
    assert canonical_race_type("ALLOWANCE OPTIONAL CLAIMING") == "ALLOWANCE OPTIONAL CLAIMING"
    assert canonical_race_type("Maiden Claiming - Fillies") == "MAIDEN CLAIMING"
    assert canonical_race_type("") is None
    assert canonical_race_type("SOMETHING ELSE") is None


def test_describe_scope_reads_cleanly():
    assert describe_scope(parse_scope("turf claiming races")) == "CLAIMING (turf)"
    assert describe_scope({}) == "all races"


# ── Selection: evidence outranks recency ────────────────────────────────────

def test_recency_arm_reproduces_the_old_behaviour_exactly():
    """The control arm has to be the OLD code path or the A/B measures nothing."""
    lessons = [L(f"lesson {i}", age_days=i) for i in range(10)]
    chosen = select_lessons(lessons, arm=ARM_RECENCY)
    assert len(chosen) == LESSON_CONTROL_LIMIT
    assert [c.text for c in chosen] == [f"lesson {i}" for i in range(LESSON_CONTROL_LIMIT)]


def test_proven_lesson_outranks_a_newer_unproven_one():
    """The exact failure that made the loop inert: a lesson written last night
    displaced one that had been earning its place."""
    proven = L("proven", verdict="PROVEN", lift=4.0, age_days=30)
    fresh = [L(f"fresh {i}", age_days=0) for i in range(10)]
    chosen = select_lessons([*fresh, proven], arm=ARM_MEASURED, limit=3)
    assert chosen[0].text == "proven"


def test_bigger_measured_lift_ranks_first():
    small = L("small", verdict="PROVEN", lift=1.0, age_days=1)
    big = L("big", verdict="PROVEN", lift=6.0, age_days=40)
    assert select_lessons([small, big], arm=ARM_MEASURED)[0].text == "big"


def test_failing_lessons_are_never_injected():
    """A lesson measurably worse than its own control is worse than no lesson."""
    failing = L("failing", verdict="FAILING", lift=-5.0, age_days=0)
    ok = L("ok", age_days=5)
    chosen = select_lessons([failing, ok], arm=ARM_MEASURED)
    assert [c.text for c in chosen] == ["ok"]


def test_retired_lessons_are_never_injected_in_either_arm():
    retired = L("retired", status="retired", age_days=0)
    live = L("live", age_days=1)
    for arm in (ARM_MEASURED, ARM_RECENCY):
        assert [c.text for c in select_lessons([retired, live], arm=arm)] == ["live"]


def test_a_continue_lesson_always_gets_a_slot():
    """Ranked purely by recency the playbook filled with CHANGE lessons, so
    Secretariat was told what to stop doing and never what to keep doing."""
    changes = [L(f"change {i}", lesson_type="change", age_days=i) for i in range(8)]
    keep = L("continue this", lesson_type="continue", age_days=40)
    chosen = select_lessons([*changes, keep], arm=ARM_MEASURED, limit=4)
    assert any(c.lesson_type == "continue" for c in chosen)
    assert len(chosen) == 4


def test_continue_guarantee_does_not_invent_one():
    changes = [L(f"change {i}", age_days=i) for i in range(4)]
    chosen = select_lessons(changes, arm=ARM_MEASURED, limit=2)
    assert len(chosen) == 2


def test_measured_arm_injects_more_than_the_old_five():
    lessons = [L(f"lesson {i}", age_days=i) for i in range(12)]
    assert len(select_lessons(lessons, arm=ARM_MEASURED)) > LESSON_CONTROL_LIMIT


# ── A/B split ───────────────────────────────────────────────────────────────

def test_arm_is_stable_for_a_race():
    """A re-run or the --only-missing second pass must never flip a race
    mid-experiment."""
    assert len({lesson_arm_for_race("SAR_123-4") for _ in range(20)}) == 1


def test_arm_split_is_roughly_even_and_independent_of_the_model_ab():
    from app.services.secretariat import pick_model_for_race

    ids = [f"TRK_{i}-{i % 9}" for i in range(3000)]
    measured = sum(lesson_arm_for_race(r) == ARM_MEASURED for r in ids)
    assert 0.4 < measured / len(ids) < 0.6

    # Different salt, so the two experiments do not assign identical races to
    # both challengers and confound each other.
    same = sum(
        (lesson_arm_for_race(r) == ARM_MEASURED)
        == (pick_model_for_race(r) != "claude-haiku-4-5-20251001")
        for r in ids
    )
    assert 0.4 < same / len(ids) < 0.6


def test_no_race_id_falls_back_to_the_control_arm():
    assert lesson_arm_for_race("") == ARM_RECENCY
    assert lesson_arm_for_race(None) == ARM_RECENCY


# ── Rendering ───────────────────────────────────────────────────────────────

def test_proven_lessons_are_labelled_with_their_numbers():
    block = render_lessons_block([L("back the chalk", verdict="PROVEN", lift=3.4)])
    assert "PROVEN: +3.4 pts" in block and "back the chalk" in block


def test_empty_playbook_renders_nothing():
    assert render_lessons_block([]) == ""


# ── Scope comes from the condition, not the rationale ───────────────────────
# Lessons read "When <condition>, I <action>, because <rationale>". The rationale
# routinely names other categories in contrast, and reading scope from it made a
# turf lesson claim dirt races — which would have scored it on races it never
# governed and produced a confidently wrong verdict.

def test_rationale_clause_does_not_widen_scope():
    from app.services.lesson_scope import condition_clause

    turf_lesson = (
        "CONTINUE: When I have a form-based win pick on turf — maiden or claiming — "
        "at a fair price ($5-$15), I should trust the selection, because turf form "
        "is more stable and predictable than dirt."
    )
    scope = parse_scope(turf_lesson)
    assert scope["surfaces"] == ["TURF"], "the contrasting 'than dirt' is not a scope"
    assert set(scope["race_types"]) == {"MAIDEN", "CLAIMING"}
    assert "because" not in condition_clause(turf_lesson).lower()


def test_condition_clause_survives_lessons_without_a_rationale():
    scope = parse_scope("CHANGE: When handicapping turf races, I stop defaulting to the favorite")
    assert scope["surfaces"] == ["TURF"]
    # No prefix, no rationale, no trailing action — still scoped.
    assert parse_scope("stakes races")["race_types"] == ["STAKES"]


def test_condition_clause_keeps_an_embedded_first_person_phrase():
    """"and I find myself" is part of the condition; only a comma-led ", I "
    starts the action clause."""
    lesson = ("CHANGE: When a claiming or maiden claiming race has a heavy chalk at "
              "$2.10–$3.40 and I find myself reaching for a longer shot, I override that instinct")
    scope = parse_scope(lesson)
    assert set(scope["race_types"]) == {"CLAIMING", "MAIDEN CLAIMING"}
    assert scope["price_band"] == [2.10, 3.40]


# ── Pick-depth experiment ───────────────────────────────────────────────────
# A full analysis costs ~$0.037/race and writes ~3,470 output tokens; the cheap
# predict path costs ~$0.001 and writes ~40. If the cheap path locks an equally
# good pick, the write-up only needs generating when someone opens the race.
# Whether it does is unmeasured, so the split has to be small and clean.

def test_lean_share_matches_the_configured_percent():
    from app.services.secretariat import PICK_DEPTH_LEAN_PERCENT, pick_depth_for_race

    ids = [f"TRK_{i}-{i % 11}" for i in range(4000)]
    lean = sum(pick_depth_for_race(r) == "lean" for r in ids) / len(ids)
    assert abs(lean * 100 - PICK_DEPTH_LEAN_PERCENT) < 4


def test_depth_is_stable_and_independent_of_the_other_experiments():
    from app.services.lesson_memory import ARM_MEASURED, lesson_arm_for_race
    from app.services.secretariat import pick_depth_for_race, pick_model_for_race

    assert len({pick_depth_for_race("SAR_9-2") for _ in range(20)}) == 1

    ids = [f"T_{i}-{i % 7}" for i in range(3000)]
    # Independent of the lesson arm: a lean race must be no likelier to be in
    # one lesson arm than the other, or the experiments confound each other.
    lean = [r for r in ids if pick_depth_for_race(r) == "lean"]
    measured = sum(lesson_arm_for_race(r) == ARM_MEASURED for r in lean) / len(lean)
    assert 0.4 < measured < 0.6
    # Independent of the model arm too. Asserted against the configured percent
    # rather than a fixed number, since that percent is set per deployment.
    from app.services.secretariat import PICK_MODEL_AB_PERCENT, PICK_MODEL_CHALLENGER
    challenger = sum(pick_model_for_race(r) == PICK_MODEL_CHALLENGER for r in lean) / len(lean)
    assert abs(challenger * 100 - PICK_MODEL_AB_PERCENT) < 6


def test_no_race_id_never_lands_in_the_lean_arm():
    from app.services.secretariat import pick_depth_for_race

    assert pick_depth_for_race("") == "full"
    assert pick_depth_for_race(None) == "full"
