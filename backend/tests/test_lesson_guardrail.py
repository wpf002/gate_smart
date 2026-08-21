"""
The reflect loop optimises for explaining yesterday's result, which reliably
produces lessons generalised from a single longshot winner. Those contradict the
calibration the same prompt carries and, in August 2026, drove the favorite-pick
rate from 44% to 16% and the win rate from ~25% to ~16%.

These tests use the actual lesson text that caused the regression.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from nightly_reflect import filter_lessons, violates_market_discipline


REAL_OFFENDERS = [
    "CHANGE: When I identify a price horse ($10+) with a genuine form or post advantage "
    "in a claiming race, I elevate it to my win pick rather than burying it in place or "
    "show, because Colonel Vargo ($17.40) won today.",
    "CHANGE: When a race features a horse priced at 5-1 to 8-1 with a recent form uptick, "
    "I surface it as a legitimate win contender rather than filtering it out.",
    "CHANGE: When building trifecta tickets in turf races, I must include at least one "
    "price horse ($10+) in my top slot.",
    "CHANGE: When my place or show pick shows stronger recent form than my designated win "
    "pick, I elevate it to win before locking my selections.",
]

REAL_KEEPERS = [
    "CHANGE: When a claiming race has a heavy chalk at $2.10-$3.40 and I find myself "
    "reaching for a longer shot, I override that instinct and put the chalk on top.",
    "CHANGE: When a horse is priced at or near even money (1-1 to 3-2), I move it to the "
    "win slot regardless of whether recent form looks modest.",
    "CHANGE: When the morning-line favorite is at $2.40-$3.60 and I am tempted to pick a "
    "different horse, I treat that as a red flag requiring explicit justification.",
    "CHANGE: When handicapping turf races I will require that my win selection has "
    "demonstrated recent turf form at a comparable distance.",
    "CHANGE: When I am ranking contenders I will explicitly map the pace shape "
    "(front-runner, presser, closer) before finalising my order.",
]


def test_rejects_the_lessons_that_caused_the_regression():
    for l in REAL_OFFENDERS:
        assert violates_market_discipline(l), f"should have been rejected: {l[:70]}"


def test_keeps_pro_discipline_and_neutral_lessons():
    for l in REAL_KEEPERS:
        assert not violates_market_discipline(l), f"wrongly rejected: {l[:70]}"


def test_exotics_value_advice_is_allowed():
    """Price belongs in the bet, not in who crosses the wire first — a lesson
    about exotic construction must survive."""
    ok = ("CONTINUE: When my win pick is at mid-range odds and I also have a secondary "
          "pick with solid form, I structure an exacta or trifecta around that pairing.")
    assert not violates_market_discipline(ok)


def test_filter_splits_and_preserves_order():
    kept, rejected = filter_lessons(REAL_KEEPERS[:2] + REAL_OFFENDERS[:1] + REAL_KEEPERS[2:3])
    assert len(rejected) == 1
    assert kept == REAL_KEEPERS[:2] + REAL_KEEPERS[2:3]


def test_handles_empty_and_none():
    assert filter_lessons([]) == ([], [])
    assert filter_lessons(None) == ([], [])
    assert not violates_market_discipline("")
    assert not violates_market_discipline(None)


def test_place_show_promotion_is_rejected():
    """The place/show pick is longer-priced by construction, so a standing
    instruction to elevate it to win is the same leak in different words."""
    l = ("CHANGE: When my place or show pick shows stronger recent form than my "
         "designated win pick, I elevate it to win before locking my selections.")
    assert violates_market_discipline(l)
