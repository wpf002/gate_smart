"""
Tests for the /meets listing-gap recovery in racing_api.

The upstream /north-america/meets listing intermittently drops individual
tracks for a date even though the track is running (observed: Saratoga
missing on a Saturday while present on the surrounding days). The per-meet
/entries endpoint still holds the full card under a deterministic meet_id
(`{TRACK}_{UTC-midnight-ms}`), so `_recover_missing_na_meets` probes it
directly for any in-season track the listing omitted.

These tests lock in that a running-but-unlisted track is recovered, and that
a genuinely-dark track is NOT fabricated.
"""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services import racing_api


def _utc_midnight_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


@pytest.mark.asyncio
async def test_recovers_track_dropped_from_listing():
    """A track in the roster but missing from /meets is recovered when its
    /entries endpoint returns a real card."""
    target = date.today()
    iso = target.isoformat()
    sar_meet_id = f"SAR_{_utc_midnight_ms(target)}"

    # /meets returned everything except Saratoga
    union = {"meets": [{"meet_id": f"GP_{_utc_midnight_ms(target)}", "track_name": "Gulfstream Park"}]}

    async def fake_entries(meet_id):
        if meet_id == sar_meet_id:
            return {"track_name": "Saratoga", "track_id": "SAR",
                    "races": [{"race_key": {"race_number": "1"}, "runners": [{}, {}]}]}
        # any other probe is a genuinely-dark track → 404-equivalent
        raise Exception("404")

    with patch.object(racing_api, "_recent_track_prefixes",
                      AsyncMock(return_value={"SAR", "GP"})), \
         patch.object(racing_api, "get_na_meet_entries", side_effect=fake_entries), \
         patch.object(racing_api, "cache_get", AsyncMock(return_value=None)), \
         patch.object(racing_api, "cache_set", AsyncMock()):
        await racing_api._recover_missing_na_meets(union, iso)

    ids = {m["meet_id"] for m in union["meets"]}
    assert sar_meet_id in ids, "Saratoga should be recovered via the entries probe"
    recovered = next(m for m in union["meets"] if m["meet_id"] == sar_meet_id)
    assert recovered["track_name"] == "Saratoga"
    assert recovered["_recovered_probe"] is True


@pytest.mark.asyncio
async def test_does_not_fabricate_dark_track():
    """A rostered track that is genuinely NOT running (entries 404s) must not
    be added — the probe is the source of truth, no invented races."""
    target = date.today()
    iso = target.isoformat()
    union = {"meets": [{"meet_id": f"GP_{_utc_midnight_ms(target)}", "track_name": "Gulfstream Park"}]}

    async def always_404(meet_id):
        raise Exception("404")

    neg_writes = []

    async def fake_cache_set(key, val, ex=None):
        neg_writes.append(key)

    with patch.object(racing_api, "_recent_track_prefixes",
                      AsyncMock(return_value={"DMR", "GP"})), \
         patch.object(racing_api, "get_na_meet_entries", side_effect=always_404), \
         patch.object(racing_api, "cache_get", AsyncMock(return_value=None)), \
         patch.object(racing_api, "cache_set", side_effect=fake_cache_set):
        await racing_api._recover_missing_na_meets(union, iso)

    ids = {m["meet_id"] for m in union["meets"]}
    assert not any(i.startswith("DMR_") for i in ids), "dark track must not be fabricated"
    # DMR should have been negative-cached to avoid re-probing
    assert any("DMR_" in k for k in neg_writes)


@pytest.mark.asyncio
async def test_negative_cache_suppresses_reprobe():
    """A track already negative-cached as dark is skipped (no entries call)."""
    target = date.today()
    iso = target.isoformat()
    union = {"meets": []}

    entries_mock = AsyncMock()

    with patch.object(racing_api, "_recent_track_prefixes",
                      AsyncMock(return_value={"DMR"})), \
         patch.object(racing_api, "get_na_meet_entries", entries_mock), \
         patch.object(racing_api, "cache_get", AsyncMock(return_value=1)), \
         patch.object(racing_api, "cache_set", AsyncMock()):
        await racing_api._recover_missing_na_meets(union, iso)

    entries_mock.assert_not_called()


@pytest.mark.asyncio
async def test_skips_far_off_dates():
    """Recovery only runs near today; a far-future date does no probing."""
    union = {"meets": []}
    roster_mock = AsyncMock(return_value={"SAR"})

    with patch.object(racing_api, "_recent_track_prefixes", roster_mock), \
         patch.object(racing_api, "get_na_meet_entries", AsyncMock()) as entries_mock:
        await racing_api._recover_missing_na_meets(union, "2099-01-01")

    roster_mock.assert_not_called()
    entries_mock.assert_not_called()


@pytest.mark.asyncio
async def test_present_track_not_reprobed():
    """A track already in the listing is not probed again."""
    target = date.today()
    iso = target.isoformat()
    gp_id = f"GP_{_utc_midnight_ms(target)}"
    union = {"meets": [{"meet_id": gp_id, "track_name": "Gulfstream Park"}]}

    entries_mock = AsyncMock()

    with patch.object(racing_api, "_recent_track_prefixes",
                      AsyncMock(return_value={"GP"})), \
         patch.object(racing_api, "get_na_meet_entries", entries_mock), \
         patch.object(racing_api, "cache_get", AsyncMock(return_value=None)), \
         patch.object(racing_api, "cache_set", AsyncMock()):
        await racing_api._recover_missing_na_meets(union, iso)

    entries_mock.assert_not_called()
