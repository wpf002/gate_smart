"""
Tests for post-time resolution in racing_api.

Upstream TheRacingAPI is inconsistent between meets: some encode
``post_time_long`` as a full epoch-ms timestamp, others as
milliseconds-since-midnight (an offset that must be added to the meet's
UTC-midnight epoch). Feeding the offset form straight into fromtimestamp()
places the race in 1970 and marks it permanently "finished" — the exact bug
seen when Monmouth Park race 8 showed "Finished" with horses still in the gate.
"""
from datetime import datetime, timezone

from app.services.racing_api import _normalize_na_race, _resolve_post_epoch_ms

# 2026-07-11 00:00:00 UTC — the midnight epoch encoded in a meet_id
MEET_MIDNIGHT_MS = 1783728000000
MEET_ID = f"MTH_{MEET_MIDNIGHT_MS}"


def test_full_epoch_passthrough():
    """A full epoch-ms value is returned unchanged (Saratoga/Gulfstream form)."""
    epoch = 1783787700000  # 2026-07-11 20:35 UTC
    assert _resolve_post_epoch_ms(epoch, "SAR_1783728000000") == epoch


def test_offset_anchored_to_meet_midnight():
    """A within-day offset is added to the meet's midnight epoch (Monmouth form)."""
    # 78060000 ms = 21:41:00 → 2026-07-11 21:41 UTC
    assert _resolve_post_epoch_ms(78060000, MEET_ID) == MEET_MIDNIGHT_MS + 78060000


def test_offset_does_not_land_in_1970():
    """The offset form must not resolve to 1970 (the finished-race bug)."""
    ms = _resolve_post_epoch_ms(78060000, MEET_ID)
    year = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).year
    assert year == 2026


def test_unresolvable_returns_none():
    """Bad inputs resolve to None so callers treat the time as unknown."""
    assert _resolve_post_epoch_ms(None, MEET_ID) is None
    assert _resolve_post_epoch_ms("abc", MEET_ID) is None
    assert _resolve_post_epoch_ms(0, MEET_ID) is None
    # Offset form but no parseable midnight epoch in the meet_id
    assert _resolve_post_epoch_ms(78060000, "MTH_notanumber") is None
    assert _resolve_post_epoch_ms(78060000, "nounderscore") is None


def test_normalize_na_race_offset_form_is_future():
    """End to end: a race with an offset-form post time normalizes to the right
    absolute datetime instead of 1970."""
    race = {"race_key": {"race_number": "8"}, "post_time_long": 78060000, "runners": []}
    meet = {"meet_id": MEET_ID, "track_name": "Monmouth Park"}
    norm = _normalize_na_race(race, meet)
    assert norm["off_dt"], "off_dt should be set"
    dt = datetime.fromisoformat(norm["off_dt"])
    assert dt == datetime(2026, 7, 11, 21, 41, tzinfo=timezone.utc)


def test_sanity_clamp_rejects_wildly_off_epoch():
    """An epoch that lands far from the meet date is refused, so a malformed
    upstream value can never resurface as a bogus 'finished' race."""
    # A small full-epoch value (1970-era) for a 2026 meet — nonsense, reject.
    assert _resolve_post_epoch_ms(90_000_000, MEET_ID) is None
    # An epoch two years off the meet date must be rejected.
    two_years_off = MEET_MIDNIGHT_MS + 730 * 86_400_000
    assert _resolve_post_epoch_ms(two_years_off, MEET_ID) is None


def test_evening_card_crossing_utc_midnight_allowed():
    """A late-evening race that posts after UTC midnight (next calendar day) is
    still within the allowed window and resolves normally."""
    # 1.5 days after meet midnight — a plausible evening/night post in local time.
    val = MEET_MIDNIGHT_MS + 36 * 3_600_000
    assert _resolve_post_epoch_ms(val, MEET_ID) == val


def test_normalize_na_race_epoch_form_unchanged():
    """A full-epoch race still normalizes to the correct datetime."""
    race = {"race_key": {"race_number": "1"}, "post_time_long": 1783787700000, "runners": []}
    meet = {"meet_id": "SAR_1783728000000", "track_name": "Saratoga"}
    norm = _normalize_na_race(race, meet)
    dt = datetime.fromisoformat(norm["off_dt"])
    assert dt == datetime.fromtimestamp(1783787700000 / 1000, tz=timezone.utc)
