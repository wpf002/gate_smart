"""The international card: folding races into countries and tracks."""
from app.api.routes.races import _fold

NAMES = {"gb": "Great Britain", "ire": "Ireland", "fr": "France"}


def _race(region, course, off, **kw):
    base = {"region": region, "course": course, "off_dt": off, "off_time": off[-5:],
            "race_id": f"rac_{course}_{off}", "race_name": "A Race",
            "distance_round": "1m", "field_size": "8", "course_id": f"crs_{course}"}
    base.update(kw)
    return base


def test_countries_lead_with_the_most_racing():
    cards = [
        _race("IRE", "Cork", "2026-09-29T14:00"),
        _race("GB", "Ayr", "2026-09-29T14:08"),
        _race("GB", "Bath", "2026-09-29T14:20"),
        _race("GB", "Ayr", "2026-09-29T14:38"),
    ]
    out = _fold(cards, NAMES)
    assert [c["region"] for c in out] == ["Great Britain", "Ireland"]
    assert out[0]["race_count"] == 3
    assert out[0]["track_count"] == 2


def test_region_codes_become_country_names():
    out = _fold([_race("FR", "Chantilly", "2026-09-29T13:00")], NAMES)
    assert out[0]["region"] == "France"
    assert out[0]["region_code"] == "fr"


def test_an_unmapped_region_keeps_its_code_rather_than_vanishing():
    out = _fold([_race("ZZ", "Somewhere", "2026-09-29T13:00")], NAMES)
    assert out[0]["region"] == "ZZ"


def test_a_race_with_no_region_is_dropped():
    assert _fold([_race("", "Nowhere", "2026-09-29T13:00")], NAMES) == []


def test_tracks_are_alphabetical_and_races_run_in_time_order():
    cards = [
        _race("GB", "Wolverhampton", "2026-09-29T16:00"),
        _race("GB", "Ayr", "2026-09-29T15:30"),
        _race("GB", "Ayr", "2026-09-29T14:00"),
    ]
    out = _fold(cards, NAMES)
    assert [t["course"] for t in out[0]["tracks"]] == ["Ayr", "Wolverhampton"]
    assert [r["off_dt"] for r in out[0]["tracks"][0]["races"]] == [
        "2026-09-29T14:00", "2026-09-29T15:30"]


def test_distance_round_is_preferred_over_the_raw_distance():
    # The feed writes "1m0f0y" or a bare "8" in `distance`; distance_round reads.
    out = _fold([_race("GB", "Ayr", "2026-09-29T14:00",
                       distance="1m0f0y", distance_round="1m")], NAMES)
    assert out[0]["tracks"][0]["races"][0]["distance"] == "1m"


def test_group_races_and_abandonments_are_flagged():
    out = _fold([_race("FR", "Longchamp", "2026-10-04T17:00",
                       big_race=True, is_abandoned=False)], NAMES)
    race = out[0]["tracks"][0]["races"][0]
    assert race["big_race"] is True and race["is_abandoned"] is False
