"""A pick only counts if it was locked before the gate opened.

On 2026-09-18 a catch-up run locked the whole card at 13:55 ET, two hours into
racing, while the feed was serving final tote odds. Those 24 picks won 41.7%
against 26.9% for honest ones and went straight into the published rate.
"""
import datetime as dt

import scripts.nightly_predict_all as n

ET_1355 = dt.datetime(2026, 9, 18, 17, 55, tzinfo=dt.timezone.utc)


def test_a_race_that_has_already_run_is_off():
    assert n.race_is_off({"off_dt": "2026-09-18T12:00:00-04:00"}, ET_1355)


def test_a_race_inside_the_lock_margin_is_off():
    # 13:56 ET with the clock at 13:55 — too late to call it a prediction.
    assert n.race_is_off({"off_dt": "2026-09-18T13:56:00-04:00"}, ET_1355)


def test_a_race_still_to_come_is_kept():
    assert not n.race_is_off({"off_dt": "2026-09-18T14:30:00-04:00"}, ET_1355)


def test_utc_and_offset_forms_agree():
    # The NA feed writes UTC; the core feed writes the track's own offset.
    assert n.race_is_off({"off_dt": "2026-09-18T16:00:00+00:00"}, ET_1355)
    assert n.race_is_off({"off_dt": "2026-09-18T16:00:00Z"}, ET_1355)
    # 19:00 at +01:00 is 18:00 UTC, five minutes after 17:55 — still to come.
    assert not n.race_is_off({"off_dt": "2026-09-18T19:00:00+01:00"}, ET_1355)


def test_a_race_with_no_readable_post_time_is_kept():
    # Dropping it would silently thin the card.
    assert not n.race_is_off({}, ET_1355)
    assert not n.race_is_off({"off_dt": "not a time"}, ET_1355)
    assert not n.race_is_off({"off_dt": "2026-09-18T12:00:00"}, ET_1355)  # naive


def test_post_times_read_as_a_clock():
    from app.services.secretariat import _clock_12h
    assert _clock_12h("13:05") == "1:05 PM"
    assert _clock_12h("00:30") == "12:30 AM"
    assert _clock_12h("12:00") == "12:00 PM"
    assert _clock_12h(None) == ""
    assert _clock_12h("TBA") == "TBA"
