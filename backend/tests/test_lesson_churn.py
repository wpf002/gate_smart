"""
Lessons must live long enough to be measured.

The nightly curator is an LLM judging lessons on how they read. It minted ~8 new
ones a night and dropped older ones, so 33 lessons were retired — every one of
them "curated out", none on evidence — while 0 ever reached a verdict. Lessons
were dying faster than they could accumulate races, which makes the entire
measurement apparatus decorative: the playbook churns on narrative and nothing
is ever actually proven or disproven.

Narrative may now propose, but it can no longer retire a lesson that is still
earning its verdict.
"""
from app.services.lesson_store import MIN_TREATED_FOR_VERDICT, _protect_reason


class Row:
    def __init__(self, **kw):
        self.__dict__.update(
            {"verdict": "PENDING", "was_injected": False, "scope_races": 0,
             "text": "a lesson"} | kw
        )


def test_a_lesson_still_gathering_evidence_survives_the_curator():
    """The exact failure: dropped at 12 races, long before 80 could decide it."""
    reason = _protect_reason(Row(was_injected=True, scope_races=12))
    assert reason and "gathering evidence" in reason


def test_a_lesson_that_has_had_its_hearing_can_be_dropped():
    assert _protect_reason(Row(was_injected=True, scope_races=MIN_TREATED_FOR_VERDICT)) is None


def test_measured_verdicts_outrank_the_curator_in_both_directions():
    # Proven stays whatever the curator thinks.
    assert _protect_reason(Row(verdict="PROVEN")) == "PROVEN"
    # Measured harmful goes, even though it is "still active".
    assert _protect_reason(Row(verdict="FAILING", was_injected=True, scope_races=5)) is None


def test_a_lesson_never_injected_gets_no_protection():
    """It has no claim to a fair hearing it never took — and without this the
    active list would grow without bound, since only the top few ever inject."""
    assert _protect_reason(Row(was_injected=False, scope_races=0)) is None


def test_protection_survives_missing_attributes():
    """Rows read back mid-migration may lack the newer columns; the nightly
    reflect run must not die on that."""
    class Bare:
        text = "x"
    assert _protect_reason(Bare()) is None
