"""
Betting text derived from the picks instead of written by Claude.

Teller scripts and the exacta box option were fields in the JSON schema, so
Sonnet wrote six extra strings for every race on a 160-250 race card. Output
tokens are ~70% of what a race analysis costs and none of that text is a
judgement — it is the selections restated in window phrasing.

The frontend already had a fallback for win/place/show; it just lacked the race
number, which is why the model's version was preferred. These build the complete
line, so nothing is lost by no longer asking for it.
"""
from app.services.bet_scripts import (
    attach_bet_scripts, build_box_option, build_teller_scripts,
)


def test_straight_bets_read_like_the_window():
    out = build_teller_scripts({"win": {"selection": "#4 Bold Runner"}}, 5)
    assert out["win"] == "Say to teller: '$2 to win on #4 Bold Runner, race 5'"


def test_exotics_use_over_phrasing_not_the_slash_selection():
    out = build_teller_scripts({"exacta": {"selection": "#4/#7"}}, 3)
    assert out["exacta"] == "Say to teller: '$2 Exacta, #4 over #7, race 3'"
    tri = build_teller_scripts({"trifecta": {"selection": "#1/#2/#3"}}, 3)
    assert "#1 over #2 over #3" in tri["trifecta"]


def test_stake_comes_from_the_models_suggestion():
    out = build_teller_scripts(
        {"win": {"selection": "#2 Horse", "stake_suggestion": "Bet $10 to win"}}, 1)
    assert "$10 to win" in out["win"]


def test_missing_race_number_drops_the_suffix_rather_than_failing():
    out = build_teller_scripts({"win": {"selection": "#4 Horse"}}, None)
    assert out["win"] == "Say to teller: '$2 to win on #4 Horse'"


def test_bets_without_a_selection_are_skipped():
    out = build_teller_scripts({"win": {"selection": ""}, "place": {}, "show": None}, 2)
    assert out == {}


def test_box_option_prices_every_ordering():
    # A 2-horse exacta box is 2 combinations, so one extra unit.
    assert build_box_option({"selection": "#4/#7"}) == "Box #4-#7 for $2 more (2 combinations)"
    # 3 horses boxed is 6 orderings, so five extra units.
    assert "6 combinations" in build_box_option({"selection": "#1/#2/#3"})
    assert "$10 more" in build_box_option({"selection": "#1/#2/#3"})


def test_box_option_is_none_for_a_single_horse():
    assert build_box_option({"selection": "#4 Horse"}) is None
    assert build_box_option({}) is None


def test_attach_fills_the_analysis_and_never_invents_bets():
    data = {"bet_recommendations": {"win": {"selection": "#4 Horse"},
                                    "exacta": {"selection": "#4/#7"}}}
    attach_bet_scripts(data, 6)
    assert data["teller_script"]["win"].endswith("race 6'")
    assert "combinations" in data["bet_recommendations"]["exacta"]["box_option"]

    empty = {"bet_recommendations": {}}
    attach_bet_scripts(empty, 6)
    assert "teller_script" not in empty


def test_whole_dollar_stakes_are_not_mangled():
    """Stripping trailing zeros to tidy "12.50" turned "$10" into "$1" — a
    tenfold understatement of the stake on the line a person reads aloud."""
    from app.services.bet_scripts import _stake_dollars

    assert _stake_dollars({"stake_suggestion": "Bet $10 to win"}) == "10"
    assert _stake_dollars({"stake_suggestion": "$100 across"}) == "100"
    assert _stake_dollars({"stake_suggestion": "$12.50 exacta"}) == "12.5"
    assert _stake_dollars({"stake_suggestion": "no dollar amount"}) == "2"
