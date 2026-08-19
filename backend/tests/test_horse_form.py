"""
Horse form archive — built from our own results because no vendor will license
past performances to an app. These tests protect the two things that make it
usable: the name key must survive punctuation differences between feeds, and an
also-ran must be recorded as "ran and finished off the board", not dropped.
"""
from app.services.horse_form import (
    extract_form_rows, horse_key, render_form_block, _format_line,
)


def _result(**kw):
    base = {
        "race_id": "SAR_1-3", "track_name": "Saratoga", "distance_f": 6.0,
        "surface": "Dirt", "going": "Fast", "race_class": "CLM 10000",
        "breed": "Thoroughbred", "winning_time": 70.2,
        "runners": [
            {"horse_name": "First Horse", "position": 1, "win_payoff": 5.4},
            {"horse_name": "Second Horse", "position": 2},
            {"horse_name": "Third Horse", "position": 3},
        ],
        "also_ran": ["Fourth Horse", "Fifth Horse"],
    }
    base.update(kw)
    return base


def test_key_survives_punctuation_differences():
    assert horse_key("O'Brien's Lad") == horse_key("OBriens Lad")
    assert horse_key("Runawey-Perry") == horse_key("Runawey Perry")
    assert horse_key("  Mixed  Case  ") == "mixed case"
    assert horse_key("") == ""


def test_charted_runners_get_finish_positions():
    rows = {r["horse_name"]: r for r in extract_form_rows(_result(), None)}
    assert rows["First Horse"]["finish_pos"] == 1
    assert rows["Third Horse"]["finish_pos"] == 3
    # field size counts the charted runners plus the also-rans
    assert rows["First Horse"]["field_size"] == 5


def test_also_rans_recorded_as_off_the_board():
    """A horse that ran and finished off the board is real form — dropping it
    would make a beaten horse look unraced."""
    rows = {r["horse_name"]: r for r in extract_form_rows(_result(), None)}
    assert "Fourth Horse" in rows and "Fifth Horse" in rows
    assert rows["Fourth Horse"]["finish_pos"] is None
    assert rows["Fourth Horse"]["field_size"] == 5


def test_race_context_is_carried_onto_every_line():
    rows = extract_form_rows(_result(), None)
    assert all(r["distance_f"] == 6.0 and r["surface"] == "Dirt"
               and r["going"] == "Fast" and r["race_class"] == "CLM 10000"
               for r in rows)


def test_duplicate_names_are_not_double_counted():
    res = _result(also_ran=["First Horse", "Fourth Horse"])  # winner echoed
    rows = extract_form_rows(res, None)
    assert len([r for r in rows if r["horse_name"] == "First Horse"]) == 1


def test_no_rows_without_race_id():
    assert extract_form_rows(_result(race_id=None), None) == []


def test_render_block_empty_when_no_history():
    assert render_form_block({}) == ""


def test_render_block_labels_off_the_board():
    class _F:
        race_date = None; finish_pos = None; field_size = 8
        track = "SAR"; distance_f = 6.0; surface = "Dirt"; going = "Fast"
        race_class = "CLM"
    assert "off/8" in _format_line(_F())
    block = render_form_block({"A Horse": ["2026-08-01 2/8 SAR 6f Dirt"]})
    assert "A Horse" in block and "PAST FORM" in block
    # The model must not read "no lines" as "unraced".
    assert "NOT that it is unraced" in block
