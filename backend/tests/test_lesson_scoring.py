"""
How a lesson earns PROVEN, and how it gets retired.

The old loop asked a language model which lessons read best. This one compares,
within the races a lesson claims to govern, the picks whose prompt carried it
against contemporaneous picks that did not. These tests hold the bar where it
was set: a verdict needs real sample size on BOTH sides, and it needs to clear
significance rather than merely point the right way.
"""
from scripts.score_lessons import MIN_TREATED, classify, two_proportion_p


def test_no_verdict_without_evidence_on_both_sides():
    """A lesson sitting in the top slots of both arms has no control group. It
    stays PENDING — we cannot measure a lesson we never withheld."""
    verdict, lift, p = classify(30, 100, 0, 0)
    assert verdict == "PENDING" and lift is None and p is None

    # Plenty of control, almost no treated.
    assert classify(2, 5, 200, 900)[0] == "PENDING"


def test_small_but_flattering_sample_is_not_proof():
    n = MIN_TREATED - 1
    assert classify(n, n, 0, 500)[0] == "PENDING"


def test_a_real_improvement_reads_as_proven():
    # 30% vs 18% over a few thousand races each — far past chance.
    verdict, lift, p = classify(600, 2000, 360, 2000)
    assert verdict == "PROVEN"
    assert lift > 0 and p < 0.05


def test_a_real_regression_reads_as_failing():
    verdict, lift, p = classify(360, 2000, 600, 2000)
    assert verdict == "FAILING"
    assert lift < 0 and p < 0.05


def test_a_small_edge_in_the_right_direction_is_still_unproven():
    """Pointing the right way is not the same as being real. This is the check
    that stops the playbook filling up with noise the way it did before."""
    verdict, lift, p = classify(105, 500, 100, 500)
    assert verdict == "UNPROVEN"
    assert lift > 0 and p > 0.05


def test_identical_rates_are_unproven_not_proven():
    verdict, lift, _ = classify(200, 1000, 200, 1000)
    assert verdict == "UNPROVEN" and abs(lift) < 1e-9


def test_p_value_is_symmetric_and_degenerate_cases_are_safe():
    assert abs(two_proportion_p(600, 2000, 360, 2000) - two_proportion_p(360, 2000, 600, 2000)) < 1e-12
    assert two_proportion_p(0, 0, 5, 10) is None      # no treated races
    assert two_proportion_p(0, 100, 0, 100) is None   # nobody won anything


def test_report_handles_a_lesson_with_no_control_group():
    """A lesson sitting in the top slots of BOTH arms is never withheld, so its
    control side is empty — and a brand-new lesson has no treated side. Both are
    normal states, and the report crashed formatting None as a percentage."""
    from scripts.lesson_report import wilson

    assert wilson(0, 0) == (0.0, 0.0)
    lo, hi = wilson(5, 20)
    assert 0.0 <= lo < 0.25 < hi <= 1.0
