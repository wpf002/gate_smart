"""The Advisor's racing tools: shaping, not the upstream feed."""
import json

import pytest

from app.services import advisor_tools as t


def test_race_number_comes_from_the_race_id():
    # race_name is the stakes name or the string "Race 4", so neither can serve.
    assert t.race_number({"race_id": "ASD_1790640000000-4"}) == 4
    assert t.race_number({"race_id": "no-suffix-here"}) is None
    assert t.race_number({}) is None


def test_a_race_called_race_4_has_no_title():
    assert t._race_title({"race_name": "Race 4"}) == ""
    assert t._race_title({"race_name": "Winnipeg Futurity"}) == "Winnipeg Futurity"


def test_relative_dates_resolve():
    import datetime
    today = datetime.date.today()
    assert t._resolve_date("today") == today.isoformat()
    assert t._resolve_date("tomorrow") == (today + datetime.timedelta(days=1)).isoformat()
    assert t._resolve_date("2026-05-02") == "2026-05-02"
    # An unparseable date falls back to today rather than raising at the model.
    assert t._resolve_date("next tuesday") == today.isoformat()


def test_track_filter_is_a_loose_match():
    assert t._matches("saratoga", "Saratoga Race Course")
    assert t._matches("", "anywhere")
    assert not t._matches("belmont", "Saratoga Race Course")


@pytest.mark.asyncio
async def test_an_unknown_tool_is_an_error_the_model_can_read():
    out = json.loads(await t.run_tool("nope", {}))
    assert "No such tool" in out["error"]


@pytest.mark.asyncio
async def test_a_failing_tool_does_not_take_the_answer_down(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("upstream down")
    monkeypatch.setitem(t._DISPATCH, "list_races", boom)
    out = json.loads(await t.run_tool("list_races", {"date": "today"}))
    assert out["error"] == "list_races is unavailable right now"


@pytest.mark.asyncio
async def test_bad_arguments_come_back_as_an_error_not_a_crash():
    out = json.loads(await t.run_tool("get_horse_record", {"wrong": 1}))
    assert "Bad arguments" in out["error"]


def test_every_declared_tool_is_dispatchable():
    assert {tool["name"] for tool in t.TOOLS} == set(t.TOOL_NAMES) == set(t._DISPATCH)


def test_the_person_tool_states_what_the_dataset_covers():
    # The same limit the profile page carries: stakes company, not a strike rate.
    desc = next(x for x in t.TOOLS if x["name"] == "get_person_record")["description"]
    assert "not an overall strike rate" in desc


# ── The connections block's course lookup ────────────────────────────────────

def test_a_course_matches_across_the_country_suffix():
    from app.services.connections import _course_key
    # The analysis endpoint writes "Belmont Park (USA)"; the NA feed writes
    # "Belmont Park". Without stripping it, no US track ever matched.
    assert _course_key("Belmont Park (USA)") == _course_key("Belmont Park")
    assert _course_key("Meydan (UAE)") == "meydan"
    assert _course_key("Newmarket") == "newmarket"


def test_a_track_record_needs_a_real_sample():
    from app.services.connections import _at_course, MIN_COURSE_STARTS
    rows = [{"course": "Saratoga (USA)", "runners": MIN_COURSE_STARTS - 1,
             "1st": 5, "win_%": 0.33, "a/e": 1.4}]
    assert _at_course(rows, "Saratoga") is None


def test_a_track_record_reads_back_the_feeds_own_figures():
    from app.services.connections import _at_course
    rows = [{"course": "Santa Anita (USA)", "runners": 642, "1st": 154,
             "win_%": 0.24, "a/e": 0.92}]
    got = _at_course(rows, "Santa Anita")
    assert got == {"course": "Santa Anita", "starts": 642, "wins": 154,
                   "win_rate": 0.24, "ae": 0.92}


def test_an_unraced_course_returns_nothing():
    from app.services.connections import _at_course
    assert _at_course([{"course": "Ascot", "runners": 200, "1st": 20}], "Saratoga") is None
    assert _at_course([], "Saratoga") is None
