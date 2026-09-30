"""The Pro endpoints: parameter shaping, not the upstream feed."""
import pytest

from app.services import racing_api as r


def test_advanced_filters_keep_only_what_was_set():
    out = r._result_filters(region="gb", going=None, race_class=[], type=["flat"],
                            min_distance_y=1200, nonsense="ignored")
    assert out == {"region": "gb", "type": ["flat"], "min_distance_y": 1200}


def test_array_filters_stay_arrays_so_httpx_repeats_the_key():
    # region_codes and friends are repeated query keys; a comma string is ignored.
    assert r._result_filters(course={"crs_1", "crs_2"})["course"].__class__ is list


def test_a_params_key_is_stable_whatever_the_dict_order():
    a = r._params_key({"b": 2, "a": [1, 2]})
    b = r._params_key({"a": [1, 2], "b": 2})
    assert a == b == "a=1,2|b=2"
    assert r._params_key({}) == "none"


def test_every_searchable_party_maps_to_its_plural_path():
    assert r.ENTITY_GROUPS["damsire"] == "damsires"
    assert set(r.ENTITY_GROUPS) == {
        "horse", "jockey", "trainer", "owner", "sire", "dam", "damsire"}


@pytest.mark.asyncio
async def test_an_unknown_entity_type_is_rejected_before_the_call():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await r.search_entity("x", "greyhound")
    with pytest.raises(HTTPException):
        await r.get_entity_results("id_1", "greyhound")


@pytest.mark.asyncio
async def test_owners_reach_the_analysis_endpoints(monkeypatch):
    seen = {}

    async def fake_get(path, params=None, cache_key=None, ttl=300):
        seen["path"] = path
        return {}

    monkeypatch.setattr(r, "_get", fake_get)
    await r.get_person_analysis("own_1", "owner", "courses")
    assert seen["path"] == "/owners/own_1/analysis/courses"
    await r.get_person_analysis("trn_1", "trainer", "jockeys")
    assert seen["path"] == "/trainers/trn_1/analysis/jockeys"


@pytest.mark.asyncio
async def test_a_plain_day_still_uses_the_dated_results_path(monkeypatch):
    seen = {}

    async def fake_get(path, params=None, cache_key=None, ttl=300):
        seen.update(path=path, params=params)
        return {"results": []}

    monkeypatch.setattr(r, "_get", fake_get)
    await r.get_results("2026-09-29")
    assert seen["path"] == "/results/2026-09-29"


@pytest.mark.asyncio
async def test_a_filtered_query_moves_to_the_advanced_endpoint(monkeypatch):
    seen = {}

    async def fake_get(path, params=None, cache_key=None, ttl=300):
        seen.update(path=path, params=params)
        return {"results": []}

    monkeypatch.setattr(r, "_get", fake_get)
    await r.get_results("2026-09-29", region="gb", going=["soft"])
    assert seen["path"] == "/results"
    # A bare date becomes a one-day window so the advanced endpoint honours it.
    assert seen["params"]["start_date"] == seen["params"]["end_date"] == "2026-09-29"
    assert seen["params"]["going"] == ["soft"]


@pytest.mark.asyncio
async def test_horse_endpoints_no_longer_refuse(monkeypatch):
    # Both raised "requires a Pro plan" outright until the upgrade.
    async def fake_get(path, params=None, cache_key=None, ttl=300):
        return {"path": path}

    monkeypatch.setattr(r, "_get", fake_get)
    assert (await r.get_horse("hrs_1"))["path"] == "/horses/hrs_1/pro"
    assert (await r.get_horse_results("hrs_1"))["path"] == "/horses/hrs_1/results"


@pytest.mark.asyncio
async def test_a_horse_results_limit_is_clamped_to_the_endpoint_maximum(monkeypatch):
    seen = {}

    async def fake_get(path, params=None, cache_key=None, ttl=300):
        seen.update(params=params)
        return {}

    monkeypatch.setattr(r, "_get", fake_get)
    await r.get_horse_results("hrs_1", limit=5000)
    assert seen["params"]["limit"] == 100


@pytest.mark.asyncio
async def test_a_core_feed_race_id_resolves_through_the_pro_racecard(monkeypatch):
    # Every international card was a dead link: the detail page asked for a
    # rac_ id and get_race only knew how to look up a NA meet.
    seen = {}

    async def fake_get(path, params=None, cache_key=None, ttl=300):
        seen["path"] = path
        return {"race_id": "rac_1", "course": "Catterick", "runners": []}

    monkeypatch.setattr(r, "_get", fake_get)
    race = await r.get_race("rac_32299222618")
    assert seen["path"] == "/racecards/rac_32299222618/pro"
    assert race["course"] == "Catterick"


@pytest.mark.asyncio
async def test_a_north_america_race_id_still_goes_to_the_meet(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("must not hit the core racecard endpoint")

    async def no_meet(meet_id):
        return {"races": []}

    monkeypatch.setattr(r, "_get", boom)
    monkeypatch.setattr(r, "get_na_meet_entries", no_meet)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await r.get_race("IND_1775520000000-1")
