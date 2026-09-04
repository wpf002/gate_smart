"""
The deep-fade demotion.

Secretariat's weakness is ordering, not finding contenders — the winner is in
its top four ~69% of the time. One inversion dominates: when it ranks a
long-priced horse first, the horse it ranked SECOND usually beats it.

Measured over 14,930 settled races, on races where the top pick is not the
favorite and is priced >= 2x the favorite's morning line: pick #1 wins 12.9%,
pick #2 wins 20.4% (n=4,318, +7.5 pts). Held out on date: +7.2 before the
cutoff, +7.7 after (n=2,039, p<0.0001). Pick #2 wins 20.4%, nowhere near the
~33.9% a favorite wins, so this reorders two horses Secretariat already chose
rather than surrendering to the market.
"""
from app.services.rerank import DEEP_FADE_RATIO, apply_deep_fade_demotion, should_demote


def _analysis():
    return {"predicted_finish": {
        "first": {"horse_name": "Longshot"},
        "second": {"horse_name": "Second Choice"},
        "third": {"horse_name": "Third"},
        "fourth": {"horse_name": "Fourth"},
    }}


def test_a_deep_fade_yields_to_its_own_second_choice():
    a = _analysis()
    assert apply_deep_fade_demotion(a, {
        "top_pick_odds": 10.0, "favorite_odds": 2.0, "top_pick_is_favorite": False})
    assert a["predicted_finish"]["first"]["horse_name"] == "Second Choice"
    assert a["predicted_finish"]["second"]["horse_name"] == "Longshot"


def test_only_the_top_two_slots_move():
    """The measurement covers the first-versus-second inversion only; nothing
    was measured about third and fourth, so nothing there is touched."""
    a = _analysis()
    apply_deep_fade_demotion(a, {
        "top_pick_odds": 10.0, "favorite_odds": 2.0, "top_pick_is_favorite": False})
    assert a["predicted_finish"]["third"]["horse_name"] == "Third"
    assert a["predicted_finish"]["fourth"]["horse_name"] == "Fourth"


def test_the_favorite_is_never_demoted():
    """Siding with the market is the case that already works — 33.9% — and must
    not be disturbed."""
    assert not should_demote(10.0, 2.0, True)
    a = _analysis()
    assert not apply_deep_fade_demotion(a, {
        "top_pick_odds": 10.0, "favorite_odds": 2.0, "top_pick_is_favorite": True})
    assert a["predicted_finish"]["first"]["horse_name"] == "Longshot"


def test_a_shallow_fade_is_left_alone():
    """Below the threshold the inversion is not measurably there, so leaving the
    model's order alone is the honest default."""
    assert not should_demote(2.0 * DEEP_FADE_RATIO - 0.01, 2.0, False)
    assert should_demote(2.0 * DEEP_FADE_RATIO, 2.0, False)


def test_missing_or_junk_odds_never_trigger_a_swap():
    """Odds are absent whenever no morning line was published or the pick could
    not be matched to a runner. An unknown price is not a deep fade."""
    for top, fav in ((None, 2.0), (10.0, None), ("", 2.0), (10.0, 0), (0, 2.0), ("abc", 2.0)):
        assert not should_demote(top, fav, False), (top, fav)


def test_a_malformed_analysis_is_returned_untouched():
    market = {"top_pick_odds": 10.0, "favorite_odds": 2.0, "top_pick_is_favorite": False}
    assert not apply_deep_fade_demotion({}, market)
    assert not apply_deep_fade_demotion({"predicted_finish": None}, market)
    assert not apply_deep_fade_demotion({"predicted_finish": {"first": {"horse_name": "A"}}}, market)
    assert not apply_deep_fade_demotion(_analysis(), {})


def test_the_nightly_job_recomputes_market_context_after_a_swap():
    """top_pick_odds/favorite/is_favorite describe the TOP PICK. Leaving them on
    the demoted horse would file every re-ranked race under the wrong price and
    corrupt every fade metric downstream."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "scripts" / "nightly_predict_all.py").read_text()
    after = src[src.index("if rerank_applied:"):]
    assert "first, second = second, first" in after[:400]
    assert "market = compute_market_context(" in after[:900]
