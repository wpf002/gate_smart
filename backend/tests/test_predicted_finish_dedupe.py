"""Tests for predicted_finish de-duplication (no impossible Morning Lines)."""
from app.services.secretariat import _dedupe_predicted_finish


def _names(result):
    pf = result["predicted_finish"]
    out = []
    for pos in ("first", "second", "third", "fourth"):
        e = pf.get(pos)
        out.append(None if e is None else (e.get("name") if isinstance(e, dict) else e))
    return out


def test_duplicate_first_and_second_collapses():
    r = {"predicted_finish": {
        "first": {"name": "Pass the Test"},
        "second": {"name": "Pass the Test"},
        "third": {"name": "Bye Bye Vicki"},
        "fourth": {"name": "Zesty American"},
    }}
    assert _names(_dedupe_predicted_finish(r)) == [
        "Pass the Test", "Bye Bye Vicki", "Zesty American", None
    ]


def test_case_and_punctuation_insensitive():
    r = {"predicted_finish": {
        "first": {"name": "O'Hara-Jones"},
        "second": {"name": "ohara jones"},
        "third": {"name": "Other"},
        "fourth": None,
    }}
    assert _names(_dedupe_predicted_finish(r)) == ["O'Hara-Jones", "Other", None, None]


def test_all_distinct_unchanged():
    r = {"predicted_finish": {
        "first": {"name": "A"}, "second": {"name": "B"},
        "third": {"name": "C"}, "fourth": {"name": "D"},
    }}
    assert _names(_dedupe_predicted_finish(r)) == ["A", "B", "C", "D"]


def test_string_entries_supported():
    r = {"predicted_finish": {"first": "A", "second": "A", "third": "B", "fourth": "B"}}
    assert _names(_dedupe_predicted_finish(r)) == ["A", "B", None, None]


def test_idempotent():
    r = {"predicted_finish": {"first": {"name": "A"}, "second": {"name": "A"}}}
    once = _dedupe_predicted_finish(r)
    twice = _dedupe_predicted_finish({"predicted_finish": dict(once["predicted_finish"])})
    assert _names(once) == _names(twice) == ["A", None, None, None]


def test_missing_or_empty_predicted_finish_is_safe():
    assert _dedupe_predicted_finish({}) == {}
    assert _dedupe_predicted_finish({"predicted_finish": None}) == {"predicted_finish": None}
