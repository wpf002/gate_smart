"""
Unit tests for secretariat._parse_json — the JSON extraction helper
introduced to fix truncated/malformed Claude responses.
"""
import pytest
import json
from app.services.secretariat import _parse_json


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------

def test_parse_clean_json_object():
    assert _parse_json('{"answer": "hello"}') == {"answer": "hello"}


def test_parse_json_with_whitespace():
    assert _parse_json('  \n{"key": 1}\n  ') == {"key": 1}


def test_parse_markdown_fenced_json():
    text = '```json\n{"answer": "hello"}\n```'
    assert _parse_json(text) == {"answer": "hello"}


def test_parse_markdown_fenced_no_language_tag():
    text = '```\n{"answer": "hello"}\n```'
    assert _parse_json(text) == {"answer": "hello"}


def test_parse_json_with_leading_prose():
    """Claude sometimes adds a sentence before the JSON object."""
    text = 'Here is the analysis:\n{"result": "ok", "value": 42}'
    result = _parse_json(text)
    assert result == {"result": "ok", "value": 42}


def test_parse_json_with_trailing_text():
    text = '{"answer": "test"}\n\nLet me know if you need more.'
    assert _parse_json(text) == {"answer": "test"}


def test_parse_nested_json():
    data = {"runners": [{"name": "Arkle", "score": 90}], "confidence": "high"}
    assert _parse_json(json.dumps(data)) == data


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_parse_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_json('{"unterminated": "string')


def test_parse_raises_on_empty_string():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_json("")


def test_parse_raises_on_no_json_object():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_json("just plain text with no braces")


# ---------------------------------------------------------------------------
# debrief_race — deterministic, no LLM
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, patch


CD_RESULTS = {
    "race_id": "CD_meet-1",
    "title": "Race 1",
    "track_name": "CHURCHILL DOWNS",
    "race_class": "MAIDEN SPECIAL WEIGHT",
    "distance_description": "1 1/16 Miles",
    "surface_description": "Dirt",
    "track_condition_description": "Fast",
    "total_purse": 118686.0,
    "winning_time": "1:41.86",
    "fractions_raw": {
        "fraction_1": {"minutes": 0, "seconds": 23, "hundredths": 11},
        "fraction_2": {"minutes": 0, "seconds": 47, "hundredths": 3},
        "fraction_3": {"minutes": 1, "seconds": 11, "hundredths": 40},
        "fraction_4": {"minutes": 1, "seconds": 35, "hundredths": 68},
        "winning_time":{"minutes": 1, "seconds": 41, "hundredths": 86},
    },
    "payoffs": [
        {"wager_name": "Win",        "winning_numbers": "11",       "base_amount": 2.0, "payoff_amount": "4.14",   "total_pool": "0"},
        {"wager_name": "Exacta",     "winning_numbers": "11-3",     "base_amount": 2.0, "payoff_amount": "10.72",  "total_pool": "838952.0"},
        {"wager_name": "Trifecta",   "winning_numbers": "11-3-4",   "base_amount": 0.5, "payoff_amount": "42.07",  "total_pool": "511491.0"},
        {"wager_name": "Superfecta", "winning_numbers": "11-3-4-6", "base_amount": 1.0, "payoff_amount": "188.44", "total_pool": "175189.0"},
        {"wager_name": "Odd or Even","winning_numbers": "ODD",      "base_amount": 0.0, "payoff_amount": "2.6",    "total_pool": "5429.0"},
    ],
    "also_ran": ["Cromwell", "Stakeholder", "Bourbon Dream"],
    "scratches": [],
    "runners": [
        {"horse_name": "Powershift",   "horse": "Powershift",   "horse_id": "h1", "position": "1", "number": "11", "jockey": "Irad Ortiz, Jr.", "trainer": "Todd Pletcher", "win_payoff": 4.14, "place_payoff": 2.7, "show_payoff": 2.4},
        {"horse_name": "Silent Way",   "horse": "Silent Way",   "horse_id": "h2", "position": "2", "number": "3",  "jockey": "Flavien Prat",    "trainer": "Peter Eurton",  "win_payoff": 0.0,  "place_payoff": 3.06, "show_payoff": 2.64},
        {"horse_name": "Ingleborough", "horse": "Ingleborough", "horse_id": "h3", "position": "3", "number": "4",  "jockey": "Martin Garcia",   "trainer": "Dale Romans",   "win_payoff": 0.0,  "place_payoff": 0.0, "show_payoff": 9.7},
    ],
}


@pytest.mark.asyncio
async def test_debrief_is_deterministic_and_makes_no_llm_call():
    """debrief_race must produce its output without ever invoking the Anthropic client."""
    from app.services import secretariat

    with patch("app.services.secretariat.client.messages.create",
               new=AsyncMock(side_effect=AssertionError("LLM was called — debrief must be deterministic"))), \
         patch("app.core.cache.cache_set", new=AsyncMock()):
        result = await secretariat.debrief_race("CD_meet-1", {}, CD_RESULTS, prior_analysis=None)

    assert result["race_id"] == "CD_meet-1"
    assert result["winning_time"] == "1:41.86"


@pytest.mark.asyncio
async def test_debrief_computes_split_by_split_pace():
    """Splits = consecutive cumulative differences. Final = winning_time - last call."""
    from app.services import secretariat

    with patch("app.core.cache.cache_set", new=AsyncMock()):
        result = await secretariat.debrief_race("CD_meet-1", {}, CD_RESULTS)

    by_call = {f["call"]: f for f in result["fractions"]}
    assert by_call["1/4"]["split"]   == ":23.11"
    assert by_call["1/4"]["cumulative"] == ":23.11"
    assert by_call["1/2"]["split"]   == ":23.92"   # 47.03 - 23.11
    assert by_call["1/2"]["cumulative"] == ":47.03"
    assert by_call["3/4"]["split"]   == ":24.37"   # 1:11.40 - :47.03
    assert by_call["Mile"]["split"]  == ":24.28"   # 1:35.68 - 1:11.40
    assert by_call["Final"]["split"] == ":06.18"   # 1:41.86 - 1:35.68
    assert by_call["Final"]["cumulative"] == "1:41.86"


@pytest.mark.asyncio
async def test_debrief_formats_payoffs_and_drops_wps_and_oddeven():
    """WPS payouts live on the runners; Odd/Even is a prop bet — neither belongs in exotics."""
    from app.services import secretariat

    with patch("app.core.cache.cache_set", new=AsyncMock()):
        result = await secretariat.debrief_race("CD_meet-1", {}, CD_RESULTS)

    wagers = [e["wager"] for e in result["exotics"]]
    assert "Win" not in wagers
    assert "Odd or Even" not in wagers
    assert wagers == ["Exacta", "Trifecta", "Superfecta"]

    exacta = result["exotics"][0]
    assert exacta["payoff"] == "$10.72"
    assert exacta["pool"]   == "$838,952"
    assert exacta["base"]   == "$2.00"

    order = result["official_order"]
    assert order[0]["win_payoff"]   == "$4.14"
    assert order[1]["win_payoff"]   is None       # zero payoff is suppressed
    assert order[1]["place_payoff"] == "$3.06"
    assert order[2]["show_payoff"]  == "$9.70"


@pytest.mark.asyncio
async def test_debrief_prediction_check_resolves_contender_finishes():
    """prediction_check looks up where each pre-race contender actually finished."""
    from app.services import secretariat

    prior = {"top_contenders": ["Powershift", "Bourbon Dream", "Cromwell"]}
    with patch("app.core.cache.cache_set", new=AsyncMock()):
        result = await secretariat.debrief_race("CD_meet-1", {}, CD_RESULTS, prior_analysis=prior)

    pc = result["prediction_check"]
    assert pc["outcome"] == "hit"   # Powershift won
    assert pc["contenders"][0] == {"horse": "Powershift",    "actual_finish": "1"}
    assert pc["contenders"][1] == {"horse": "Bourbon Dream", "actual_finish": "Out of money"}
    assert pc["contenders"][2] == {"horse": "Cromwell",      "actual_finish": "Out of money"}


@pytest.mark.asyncio
async def test_debrief_prediction_check_partial_when_top_pick_runs_2nd_or_3rd():
    from app.services import secretariat

    prior = {"top_contenders": ["Silent Way"]}   # finished 2nd
    with patch("app.core.cache.cache_set", new=AsyncMock()):
        result = await secretariat.debrief_race("CD_meet-1", {}, CD_RESULTS, prior_analysis=prior)
    assert result["prediction_check"]["outcome"] == "partial"


@pytest.mark.asyncio
async def test_debrief_prediction_check_is_null_without_prior_analysis():
    from app.services import secretariat

    with patch("app.core.cache.cache_set", new=AsyncMock()):
        result = await secretariat.debrief_race("CD_meet-1", {}, CD_RESULTS, prior_analysis=None)
    assert result["prediction_check"] is None


