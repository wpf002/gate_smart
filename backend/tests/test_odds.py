"""Tests for odds parsing + market-context derivation."""
import pytest

from app.services.odds import compute_market_context, parse_odds_to_decimal


@pytest.mark.parametrize("raw,expected", [
    ("5/2", 2.5),
    ("9/5", 1.8),
    ("7-2", 3.5),
    ("even", 1.0),
    ("evs", 1.0),
    ("evens", 1.0),
    ("1/1", 1.0),
    ("3", 3.0),
    ("10", 10.0),
])
def test_parse_valid_odds(raw, expected):
    assert parse_odds_to_decimal(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "  ", "SCR", "scratched", "n/a", "-", "5/0", "abc"])
def test_parse_invalid_odds(raw):
    assert parse_odds_to_decimal(raw) is None


def _runner(num, name, odds, scratched=False):
    return {"program_number": num, "horse_name": name, "odds": odds, "scratched": scratched}


def test_market_context_picks_favorite():
    runners = [
        _runner("1", "Alpha", "5/1"),
        _runner("2", "Bravo", "9/5"),   # favorite (lowest)
        _runner("3", "Charlie", "3/1"),
    ]
    m = compute_market_context(runners, pick_name="Bravo", pick_num="2")
    assert m["field_size"] == 3
    assert m["favorite_num"] == "2"
    assert m["favorite_odds"] == pytest.approx(1.8)
    assert m["top_pick_odds"] == pytest.approx(1.8)
    assert m["top_pick_is_favorite"] is True


def test_market_context_pick_not_favorite():
    runners = [
        _runner("1", "Alpha", "5/1"),
        _runner("2", "Bravo", "9/5"),   # favorite
        _runner("3", "Charlie", "3/1"),
    ]
    m = compute_market_context(runners, pick_name="Charlie", pick_num="3")
    assert m["favorite_num"] == "2"
    assert m["top_pick_odds"] == pytest.approx(3.0)
    assert m["top_pick_is_favorite"] is False


def test_market_context_excludes_scratched_from_field_and_favorite():
    runners = [
        _runner("1", "Alpha", "1/5", scratched=True),  # lowest odds but scratched
        _runner("2", "Bravo", "9/5"),                  # true favorite among active
        _runner("3", "Charlie", "3/1"),
    ]
    m = compute_market_context(runners, pick_name="Bravo", pick_num="2")
    assert m["field_size"] == 2
    assert m["favorite_num"] == "2"
    assert m["top_pick_is_favorite"] is True


def test_market_context_match_by_name_when_num_missing():
    runners = [_runner("1", "Alpha", "5/1"), _runner("2", "Bravo Star", "2/1")]
    m = compute_market_context(runners, pick_name="bravo star", pick_num=None)
    assert m["top_pick_odds"] == pytest.approx(2.0)


def test_market_context_no_odds_published():
    runners = [_runner("1", "Alpha", ""), _runner("2", "Bravo", None)]
    m = compute_market_context(runners, pick_name="Alpha", pick_num="1")
    assert m["field_size"] == 2
    assert m["favorite_num"] is None
    assert m["favorite_odds"] is None
    assert m["top_pick_is_favorite"] is None


def test_market_context_empty_runners():
    m = compute_market_context([], pick_name="Alpha", pick_num="1")
    assert m["field_size"] is None
    assert all(m[k] is None for k in m)
