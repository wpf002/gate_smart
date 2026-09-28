"""
Bet slips and pick contests.

Two constraints hold everything here. Payouts come only from the official chart —
a leg without an official price is "unpriced", never shown as a win or a loss.
And contests involve no wagering and no prizes; they score calls, nothing more.
"""
from datetime import date

from app.services.contest import (
    BET_TYPES, POINTS_BEAT_BONUS, POINTS_CORRECT, beat_secretariat_streak, best_streak,
    bet_hit, bet_payoff, pick_day_streak, score_pick,
)
from app.services.ticket import build_ticket, grade_ticket, per_stake, ticket_summary

PICKS = [{"name": "Alpha", "number": "7"}, {"name": "Bravo", "number": "1"},
         {"name": "Charlie", "number": "2"}]

# Shape of one race from the live results feed (Gulfstream R1, 2026-09-13).
RESULT = {
    "runners": [{"program_number": "7", "horse_name": "Alpha", "win_payoff": "5.80"},
                {"program_number": "1", "horse_name": "Bravo"},
                {"program_number": "2", "horse_name": "Charlie"}],
    "payoffs": [
        {"wager_type": "E", "base_amount": 2.0, "payoff_amount": "19.6", "winning_numbers": "7-1"},
        {"wager_type": "T", "base_amount": 0.5, "payoff_amount": "45.4", "winning_numbers": "7-1-2"},
    ],
}


# ── Ticket ──────────────────────────────────────────────────────────────────

def test_exotic_payouts_are_restated_per_2_dollars():
    """A $0.50 trifecta paying $45.40 is $181.60 on a $2 ticket. Showing the raw
    figure would understate the trifecta fourfold next to the win leg."""
    assert per_stake("45.4", 0.5) == 181.60
    assert per_stake("19.6", 2.0) == 19.60
    assert per_stake("", 2.0) is None
    assert per_stake("10", 0) is None


def test_ticket_explains_what_to_say_at_the_window():
    legs = build_ticket(PICKS, race_number=1)
    assert [l["type"] for l in legs] == ["win", "exacta", "trifecta"]
    assert legs[0]["say"] == "$2 to win on #7, race 1"
    assert legs[2]["say"] == "$2 trifecta 7-1-2, race 1"


def test_a_leg_is_never_built_without_program_numbers():
    """Telling someone to bet a horse without its number isn't a bet they can place."""
    legs = build_ticket([{"name": "Alpha", "number": "7"}, {"name": "Bravo", "number": ""}], 1)
    assert [l["type"] for l in legs] == ["win"]


def test_hits_carry_the_official_price():
    graded = grade_ticket(build_ticket(PICKS, 1), RESULT)
    by = {l["type"]: l for l in graded}
    assert by["win"]["status"] == "hit" and by["win"]["payout"] == 5.80
    assert by["exacta"]["status"] == "hit" and by["exacta"]["payout"] == 19.60
    assert by["trifecta"]["status"] == "hit" and by["trifecta"]["payout"] == 181.60


def test_misses_show_what_actually_won():
    picks = [{"name": "Bravo", "number": "1"}, {"name": "Alpha", "number": "7"},
             {"name": "Charlie", "number": "2"}]
    by = {l["type"]: l for l in grade_ticket(build_ticket(picks, 1), RESULT)}
    assert by["win"]["status"] == "miss" and by["win"]["winning_numbers"] == ["7"]
    assert by["exacta"]["status"] == "miss" and by["exacta"]["winning_numbers"] == ["7", "1"]
    assert by["win"]["payout"] is None


def test_a_missing_pool_is_unpriced_not_a_loss():
    """Small fields often run with no trifecta pool. Scoring that as a lost $2
    would invent a loss that never happened."""
    no_tri = {**RESULT, "payoffs": [p for p in RESULT["payoffs"] if p["wager_type"] != "T"]}
    by = {l["type"]: l for l in grade_ticket(build_ticket(PICKS, 1), no_tri)}
    assert by["trifecta"]["status"] == "unpriced"
    summary = ticket_summary(list(by.values()))
    assert summary["legs_priced"] == 2 and summary["staked"] == 4.0


def test_no_result_yet_leaves_the_ticket_pending():
    legs = grade_ticket(build_ticket(PICKS, 1), {"runners": [], "payoffs": []})
    assert all(l["status"] == "pending" for l in legs)


def test_summary_nets_returns_against_stakes():
    s = ticket_summary(grade_ticket(build_ticket(PICKS, 1), RESULT))
    assert s == {"legs_priced": 3, "hits": 3, "staked": 6.0, "returned": 207.0, "net": 201.0}


# ── Contest scoring ─────────────────────────────────────────────────────────

def test_correct_winner_scores_and_beating_secretariat_adds_the_bonus():
    assert score_pick("alpha", "alpha", "alpha")["points"] == POINTS_CORRECT
    beat = score_pick("alpha", "alpha", "bravo")
    assert beat["beat_secretariat"] and beat["points"] == POINTS_CORRECT + POINTS_BEAT_BONUS


def test_a_miss_scores_nothing_and_never_goes_negative():
    miss = score_pick("bravo", "alpha", "alpha")
    assert miss == {"correct": False, "secretariat_correct": True,
                    "beat_secretariat": False, "points": 0}


def test_no_secretariat_pick_means_no_beat_bonus():
    """A race Secretariat didn't call can't be a race you beat it in."""
    graded = score_pick("alpha", "alpha", None)
    assert graded["secretariat_correct"] is None and not graded["beat_secretariat"]
    assert graded["points"] == POINTS_CORRECT


# ── Streaks ─────────────────────────────────────────────────────────────────

def test_pick_day_streak_survives_until_today_is_picked():
    today = date(2026, 9, 13)
    days = [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)]
    assert pick_day_streak(days, today) == 3          # yesterday still counts
    assert pick_day_streak(days + [today], today) == 4
    assert pick_day_streak([date(2026, 9, 9)], today) == 0
    assert pick_day_streak([], today) == 0


def test_beat_streak_extends_on_beats_holds_on_ties_and_breaks_on_misses():
    beat = {"correct": True, "beat_secretariat": True}
    tie = {"correct": True, "beat_secretariat": False}
    miss = {"correct": False, "beat_secretariat": False}
    assert beat_secretariat_streak([beat, beat]) == 2
    assert beat_secretariat_streak([beat, tie, beat]) == 2   # tie doesn't break it
    assert beat_secretariat_streak([beat, miss, beat]) == 1  # the miss does
    assert beat_secretariat_streak([]) == 0


def test_best_streak_finds_the_longest_run():
    assert best_streak([True, True, False, True, True, True, False]) == 3
    assert best_streak([]) == 0


# ── Bet types: win, place, show, exacta, trifecta ────────────────────────────

# A chart the way the results feed serves it: top 3 in finish order, each with
# the payoffs for the pools that actually ran, plus the exotic pools.
CHART = {
    "runners": [
        {"horse_name": "Alpha", "program_number": "7",
         "win_payoff": "5.80", "place_payoff": "3.60", "show_payoff": "2.80"},
        {"horse_name": "Bravo", "program_number": "1",
         "place_payoff": "4.20", "show_payoff": "3.20"},
        {"horse_name": "Charlie", "program_number": "2", "show_payoff": "6.40"},
    ],
    "payoffs": [
        {"wager_type": "E", "base_amount": 2.0, "payoff_amount": "19.6", "winning_numbers": "7-1"},
        {"wager_type": "T", "base_amount": 0.5, "payoff_amount": "24.35", "winning_numbers": "7-1-2"},
    ],
}
FINISH = ["alpha", "bravo", "charlie"]


def test_a_straight_bet_lands_anywhere_inside_its_depth():
    # Charlie ran third: a losing win and place bet, a winning show bet.
    assert bet_hit("win", ["charlie"], FINISH) is False
    assert bet_hit("place", ["charlie"], FINISH) is False
    assert bet_hit("show", ["charlie"], FINISH) is True
    assert bet_hit("place", ["bravo"], FINISH) is True


def test_exotics_need_the_exact_order():
    assert bet_hit("exacta", ["alpha", "bravo"], FINISH) is True
    assert bet_hit("exacta", ["bravo", "alpha"], FINISH) is False
    assert bet_hit("trifecta", ["alpha", "bravo", "charlie"], FINISH) is True
    assert bet_hit("trifecta", ["alpha", "charlie", "bravo"], FINISH) is False


def test_a_chart_too_short_to_grade_the_bet_returns_unknown_not_a_loss():
    assert bet_hit("trifecta", ["alpha", "bravo", "charlie"], ["alpha", "bravo"]) is None
    assert bet_hit("exacta", ["alpha", "bravo"], ["alpha"]) is None


def test_payoffs_come_from_the_chart_and_are_restated_per_two_dollars():
    assert bet_payoff("win", ["alpha"], CHART) == 5.80
    assert bet_payoff("show", ["charlie"], CHART) == 6.40
    # $2 exacta base, so the price stands as quoted.
    assert bet_payoff("exacta", ["alpha", "bravo"], CHART) == 19.6
    # 50c trifecta base restated to $2: 24.35 / 0.5 * 2.
    assert bet_payoff("trifecta", ["alpha", "bravo", "charlie"], CHART) == 97.4


def test_a_losing_bet_returns_zero_and_an_unrun_pool_returns_nothing():
    assert bet_payoff("win", ["bravo"], CHART) == 0.0
    # No show pool ran in this race, so a show bet could not have been placed —
    # that is not a loss.
    no_show = {"runners": [dict(r) for r in CHART["runners"]], "payoffs": []}
    for r in no_show["runners"]:
        r.pop("show_payoff", None)
    assert bet_payoff("show", ["alpha"], no_show) is None
    # Nor did this race offer a trifecta.
    assert bet_payoff("trifecta", ["alpha", "bravo", "charlie"], no_show) is None


def test_points_scale_with_how_hard_the_bet_is():
    assert score_pick("charlie", "alpha", None, "show", True)["points"] == BET_TYPES["show"]["points"]
    assert score_pick("alpha", "alpha", None, "win", True)["points"] == POINTS_CORRECT
    assert score_pick("alpha", "alpha", None, "trifecta", True)["points"] == BET_TYPES["trifecta"]["points"]
    assert BET_TYPES["show"]["points"] < POINTS_CORRECT < BET_TYPES["trifecta"]["points"]


def test_an_exotic_that_lands_while_secretariat_misses_still_takes_the_bonus():
    # Your exacta landed; Secretariat's top pick (yankee) didn't win.
    graded = score_pick("alpha", "alpha", "yankee", "exacta", True)
    assert graded["beat_secretariat"] is True
    assert graded["points"] == BET_TYPES["exacta"]["points"] + POINTS_BEAT_BONUS


def test_a_pick_made_before_bet_types_existed_still_grades_as_a_win_bet():
    # No bet_type, no hit flag: falls back to "your horse won", worth 10.
    assert score_pick("alpha", "alpha", None) == score_pick("alpha", "alpha", None, "win", True)
    assert score_pick("alpha", "bravo", None)["points"] == 0
