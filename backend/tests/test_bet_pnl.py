"""
Flat-bet P&L must be computed only from official chart payoffs — never
estimated from morning-line odds, and never scoring an unpriced race as a loss.
"""
from app.services.bet_pnl import compute_flat_bet_pnl, extract_top_pick_payoffs


def _result(runners):
    return {"runners": runners}


def _r(name, pos, win=0.0, place=0.0, show=0.0):
    return {"horse_name": name, "position": str(pos),
            "win_payoff": win, "place_payoff": place, "show_payoff": show}


# ── extract_top_pick_payoffs ────────────────────────────────────────────────

def test_winner_returns_all_three_payoffs():
    res = _result([_r("Frolicking", 1, 4.0, 2.64, 2.10), _r("Glow", 2, 0, 3.36, 2.24)])
    assert extract_top_pick_payoffs(res, "Frolicking") == {"win": 4.0, "place": 2.64, "show": 2.10}


def test_runner_up_returns_place_and_show_only():
    res = _result([_r("Frolicking", 1, 4.0, 2.64, 2.10), _r("Glow", 2, 0, 3.36, 2.24)])
    assert extract_top_pick_payoffs(res, "Glow") == {"win": 0.0, "place": 3.36, "show": 2.24}


def test_off_the_board_pick_loses_everything():
    res = _result([_r("Frolicking", 1, 4.0, 2.64, 2.10)])
    assert extract_top_pick_payoffs(res, "Nowhere Horse") == {"win": 0.0, "place": 0.0, "show": 0.0}


def test_unpriced_chart_returns_none_not_a_loss():
    """A chart with no winner payoff yet must be excluded, not scored 0."""
    res = _result([_r("Frolicking", 1, 0.0, 0.0, 0.0)])
    assert extract_top_pick_payoffs(res, "Frolicking") is None
    assert extract_top_pick_payoffs({"runners": []}, "Frolicking") is None


def test_name_matching_ignores_case_and_punctuation():
    res = _result([_r("O'Brien's Lad", 1, 6.0, 3.0, 2.4)])
    assert extract_top_pick_payoffs(res, "obriens lad")["win"] == 6.0


# ── compute_flat_bet_pnl ────────────────────────────────────────────────────

def test_win_pnl_matches_hand_calculation():
    rows = [
        {"top_pick_win_payoff": 4.0, "top_pick_place_payoff": 2.64, "top_pick_show_payoff": 2.10},
        {"top_pick_win_payoff": 0.0, "top_pick_place_payoff": 0.0, "top_pick_show_payoff": 0.0},
    ]
    p = compute_flat_bet_pnl(rows)
    assert p["races"] == 2
    # $2 x 2 races = $4 staked; returns $4.00 -> break even
    assert {k: p["win"][k] for k in ("staked", "returned", "net", "roi")} == {
        "staked": 4.0, "returned": 4.0, "net": 0.0, "roi": 0.0}


def test_breakeven_rate_is_the_hit_rate_that_returns_the_stake():
    # One winner in four at $8.00 returns $8 on $8 staked, so 25% is exactly
    # break-even at that price — and the gap between hit and need is zero.
    rows = [{"top_pick_win_payoff": v} for v in (8.0, 0.0, 0.0, 0.0)]
    win = compute_flat_bet_pnl(rows)["win"]
    assert win["hit_rate"] == 0.25
    assert win["avg_payoff"] == 8.0
    assert win["breakeven_rate"] == 0.25
    assert win["gap"] == 0.0
    assert win["roi"] == 0.0


def test_a_losing_strategy_shows_a_negative_gap():
    # 20% at $8.00 returns $8 on $10 staked: needed 25%, hit 20%, -5 points.
    rows = [{"top_pick_win_payoff": v} for v in (8.0, 0.0, 0.0, 0.0, 0.0)]
    win = compute_flat_bet_pnl(rows)["win"]
    assert win["hit_rate"] == 0.2
    assert win["breakeven_rate"] == 0.25
    assert win["gap"] == -0.05
    assert win["roi"] == -0.2


def test_a_strategy_that_never_cashed_has_no_breakeven_to_quote():
    win = compute_flat_bet_pnl([{"top_pick_win_payoff": 0.0}] * 3)["win"]
    assert win["hit_rate"] == 0.0
    assert win["breakeven_rate"] is None   # no price was ever paid to divide by
    assert "gap" not in win


def test_across_the_board_stakes_three_bets_per_race():
    rows = [{"top_pick_win_payoff": 4.0, "top_pick_place_payoff": 2.64, "top_pick_show_payoff": 2.10}]
    p = compute_flat_bet_pnl(rows)
    assert p["across_the_board"]["staked"] == 6.0          # $2 win + $2 place + $2 show
    assert p["across_the_board"]["returned"] == 8.74       # 4.00 + 2.64 + 2.10
    assert p["across_the_board"]["net"] == 2.74


def test_unpriced_rows_excluded_from_denominator():
    rows = [
        {"top_pick_win_payoff": 4.0, "top_pick_place_payoff": 0.0, "top_pick_show_payoff": 0.0},
        {"top_pick_win_payoff": None, "top_pick_place_payoff": None, "top_pick_show_payoff": None},
    ]
    p = compute_flat_bet_pnl(rows)
    assert p["races"] == 1 and p["unpriced_races"] == 1
    assert p["win"]["staked"] == 2.0  # not 4.0 — the unpriced race isn't a bet


def test_losing_day_reports_negative_roi():
    rows = [{"top_pick_win_payoff": 0.0, "top_pick_place_payoff": 0.0, "top_pick_show_payoff": 0.0}] * 5
    p = compute_flat_bet_pnl(rows)
    assert p["win"]["net"] == -10.0
    assert p["win"]["roi"] == -1.0


def test_empty_input_is_safe():
    p = compute_flat_bet_pnl([])
    assert p["races"] == 0 and p["win"]["roi"] == 0.0


# ── Missing betting pools ───────────────────────────────────────────────────
# Small fields often have no show pool (sometimes no place pool). A bet that
# could not have been placed must never be scored as a loss.

def test_no_show_pool_detected_from_winner():
    """Winner has win+place but no show payoff -> race had no show pool."""
    res = _result([_r("Amour de La Vie", 1, 2.8, 2.2, 0.0), _r("Eyesonthecandy", 2, 0, 3.0, 0.0)])
    p = extract_top_pick_payoffs(res, "Amour de La Vie")
    assert p["win"] == 2.8 and p["place"] == 2.2
    assert p["show"] is None  # not 0.0 — the bet was impossible, not lost


def test_off_the_board_pick_only_loses_pools_that_existed():
    res = _result([_r("Winner", 1, 5.0, 2.4, 0.0)])
    p = extract_top_pick_payoffs(res, "Some Other Horse")
    assert p == {"win": 0.0, "place": 0.0, "show": None}


def test_unavailable_pools_are_not_staked():
    rows = [
        # show pool absent in both races -> across-the-board is only 2 bets/race
        {"top_pick_win_payoff": 2.8, "top_pick_place_payoff": 2.2, "top_pick_show_payoff": None},
        {"top_pick_win_payoff": 0.0, "top_pick_place_payoff": 0.0, "top_pick_show_payoff": None},
    ]
    p = compute_flat_bet_pnl(rows)
    assert p["across_the_board"]["staked"] == 8.0     # (2 win + 2 place) x $2
    assert p["across_the_board"]["returned"] == 5.0   # 2.80 + 2.20
    assert p["win"]["staked"] == 4.0


def test_missing_pool_does_not_invent_a_loss():
    """A race with only a win pool must not be charged for place/show stakes."""
    rows = [{"top_pick_win_payoff": 10.0, "top_pick_place_payoff": None, "top_pick_show_payoff": None}]
    p = compute_flat_bet_pnl(rows)
    assert p["across_the_board"]["staked"] == 2.0
    assert p["across_the_board"]["net"] == 8.0


# ── Edge over a name drawn from the same field ───────────────────────────────

def test_random_baseline_scales_with_field_size():
    """One winner, two place spots and three show spots per field.

    This is the only baseline our own rows can supply, and it's what separates
    "the picks are wrong" from "the picks are right and the price is dearer".
    """
    rows = [{"field_size": 8, "top_pick_win_payoff": 8.0,
             "top_pick_place_payoff": 3.0, "top_pick_show_payoff": 2.4}] * 4
    p = compute_flat_bet_pnl(rows)
    assert p["win"]["random_rate"] == 0.125      # 1 of 8
    assert p["place"]["random_rate"] == 0.25     # 2 of 8
    assert p["show"]["random_rate"] == 0.375     # 3 of 8


def test_a_short_field_cannot_give_a_random_rate_above_one():
    # Three show spots in a four-horse field is 75%, not 100% — but in a
    # three-horse field every runner shows, so the rate caps at 1.
    rows = [{"field_size": 3, "top_pick_win_payoff": 4.0,
             "top_pick_place_payoff": 2.4, "top_pick_show_payoff": 2.1}]
    p = compute_flat_bet_pnl(rows)
    assert p["show"]["random_rate"] == 1.0
    assert p["place"]["random_rate"] == round(2 / 3, 4)


def test_lift_is_the_hit_rate_over_the_random_rate():
    # Two winners in four 8-horse fields: 50% against a 12.5% baseline.
    rows = [{"field_size": 8, "top_pick_win_payoff": v} for v in (6.0, 6.0, 0.0, 0.0)]
    win = compute_flat_bet_pnl(rows)["win"]
    assert win["hit_rate"] == 0.5
    assert win["lift"] == 4.0


def test_no_field_size_means_no_baseline_rather_than_a_wrong_one():
    rows = [{"top_pick_win_payoff": 6.0}, {"top_pick_win_payoff": 0.0}]
    win = compute_flat_bet_pnl(rows)["win"]
    assert win["random_rate"] is None
    assert win["lift"] is None
    # The break-even bar doesn't depend on the field, so it still stands.
    assert win["breakeven_rate"] == round(2 / 6, 4)
