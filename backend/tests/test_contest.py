

# ── What actually happened to a settled bet ──────────────────────────────────

def test_the_official_finish_keeps_the_top_four():
    from app.services.contest import official_finish
    runners = [{"horse_name": f"H{i}", "program_number": str(i), "position": i}
               for i in range(1, 8)]
    fin = official_finish(runners)
    assert [f["position"] for f in fin] == [1, 2, 3, 4]
    assert fin[0] == {"position": 1, "name": "H1", "number": "1"}


def test_a_trifecta_with_the_right_three_in_the_wrong_order_says_so():
    # Will's 6-1-4 came back 6-4-1: all three horses, 2nd and 3rd swapped.
    # "+0" alone read exactly like a ticket that had nothing.
    from app.services.contest import result_note
    fin = [{"position": 1, "name": "Clippity Cop", "number": "6"},
           {"position": 2, "name": "Not True", "number": "4"},
           {"position": 3, "name": "Jaya Rules", "number": "1"}]
    note = result_note(["clippity cop", "jaya rules", "not true"], "trifecta", fin, False)
    assert note == "Had all of them, wrong order"


def test_an_exotic_that_only_had_the_winner_says_that_instead():
    from app.services.contest import result_note
    fin = [{"position": 1, "name": "A", "number": "1"},
           {"position": 2, "name": "B", "number": "2"},
           {"position": 3, "name": "C", "number": "3"}]
    assert result_note(["a", "z", "y"], "trifecta", fin, False) == "Had the winner, wrong order"


def test_a_straight_bet_says_where_it_finished():
    from app.services.contest import result_note
    fin = [{"position": 1, "name": "A", "number": "1"},
           {"position": 2, "name": "B", "number": "2"},
           {"position": 3, "name": "C", "number": "3"}]
    assert result_note(["b"], "win", fin, False) == "Finished 2, needed top 1"
    assert result_note(["z"], "win", fin, False) == "Ran out of the money"


def test_a_winning_bet_needs_no_explanation():
    from app.services.contest import result_note
    fin = [{"position": 1, "name": "A", "number": "1"}]
    assert result_note(["a"], "win", fin, True) == ""


def test_a_core_feed_pick_is_dated_from_its_post_time():
    # rac_32299222618 has no epoch in it; reading the serial as one put every
    # international pick in 1971.
    import datetime as dt
    from zoneinfo import ZoneInfo
    from app.services.contest import racing_day
    off = dt.datetime(2026, 9, 30, 14, 8, tzinfo=ZoneInfo("Europe/London"))
    assert racing_day("rac_32299222618", off) == dt.date(2026, 9, 30)
    assert racing_day("IND_1790640000000-1") == dt.date(2026, 9, 29)
