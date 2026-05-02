"""
Tests for GET /api/races/* — racing_api service is mocked throughout.
Routes now use NA-only functions (get_na_racecards_full, get_na_results_full).
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

FAKE_NA_RACECARDS = {"racecards": [{"race_id": "IND_1775520000000-1", "course": "Indianapolis"}]}
FAKE_RACE = {"race_id": "IND_1775520000000-1", "course": "Indianapolis", "runners": []}
FAKE_NA_RESULTS = {"results": [{"race_id": "IND_1775520000000-1", "runners": []}]}


@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /races/today
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_races_today_returns_api_data(client):
    with patch("app.api.routes.races.racing_api.get_na_racecards_full",
               new=AsyncMock(return_value=FAKE_NA_RACECARDS)):
        r = await client.get("/api/races/today")
    assert r.status_code == 200
    assert r.json() == FAKE_NA_RACECARDS


@pytest.mark.asyncio
async def test_races_today_calls_na_function(client):
    mock = AsyncMock(return_value=FAKE_NA_RACECARDS)
    with patch("app.api.routes.races.racing_api.get_na_racecards_full", new=mock):
        await client.get("/api/races/today")
    mock.assert_called_once()


@pytest.mark.asyncio
async def test_races_today_propagates_502(client):
    with patch("app.api.routes.races.racing_api.get_na_racecards_full",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 401"))):
        r = await client.get("/api/races/today")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_races_today_wraps_unexpected_errors(client):
    with patch("app.api.routes.races.racing_api.get_na_racecards_full",
               new=AsyncMock(side_effect=RuntimeError("connection reset"))):
        r = await client.get("/api/races/today")
    assert r.status_code == 502
    assert r.json()["detail"] == "Racing data unavailable"


# ---------------------------------------------------------------------------
# GET /races/date/{race_date}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_races_by_date(client):
    mock = AsyncMock(return_value=FAKE_NA_RACECARDS)
    with patch("app.api.routes.races.racing_api.get_na_racecards_full", new=mock):
        r = await client.get("/api/races/date/2026-04-05")
    assert r.status_code == 200
    mock.assert_called_once_with(date="2026-04-05")


# ---------------------------------------------------------------------------
# GET /races/results/today
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_today(client):
    mock = AsyncMock(return_value=FAKE_NA_RESULTS)
    with patch("app.api.routes.races.racing_api.get_na_results_full", new=mock):
        r = await client.get("/api/races/results/today")
    assert r.status_code == 200
    assert r.json() == FAKE_NA_RESULTS
    mock.assert_called_once()


# ---------------------------------------------------------------------------
# GET /races/results/{result_date}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_by_date(client):
    mock = AsyncMock(return_value=FAKE_NA_RESULTS)
    with patch("app.api.routes.races.racing_api.get_na_results_full", new=mock):
        r = await client.get("/api/races/results/2026-04-05")
    assert r.status_code == 200
    mock.assert_called_once_with(date="2026-04-05")


# ---------------------------------------------------------------------------
# GET /races/{race_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_race_detail(client):
    mock = AsyncMock(return_value=FAKE_RACE)
    with patch("app.api.routes.races.racing_api.get_race", new=mock):
        r = await client.get("/api/races/IND_1775520000000-1")
    assert r.status_code == 200
    assert r.json() == FAKE_RACE
    mock.assert_called_once_with("IND_1775520000000-1")


@pytest.mark.asyncio
async def test_race_detail_propagates_502(client):
    with patch("app.api.routes.races.racing_api.get_race",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 404"))):
        r = await client.get("/api/races/unknown-meet-99")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# Route ordering — literal paths must not be captured by /{race_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_today_not_captured_by_race_id_wildcard(client):
    """GET /races/results/today must hit results_today(), not race_detail()."""
    results_mock = AsyncMock(return_value=FAKE_NA_RESULTS)
    race_mock = AsyncMock(return_value=FAKE_RACE)
    with patch("app.api.routes.races.racing_api.get_na_results_full", new=results_mock), \
         patch("app.api.routes.races.racing_api.get_race", new=race_mock):
        await client.get("/api/races/results/today")
    results_mock.assert_called_once()
    race_mock.assert_not_called()


# ---------------------------------------------------------------------------
# GET /races/results/race/{race_id} — empty-position guard
# ---------------------------------------------------------------------------

def _na_meet_results(runners_data: list, race_number: str = "8") -> dict:
    return {
        "races": [
            {
                "race_key": {"race_number": int(race_number)},
                "race_name": "Test Race",
                "runners": runners_data,
            }
        ]
    }


@pytest.mark.asyncio
async def test_results_for_race_404_when_all_positions_blank(client):
    """Racing feed flagged the race finished but hasn't synced positions —
    return 404 so the frontend can show 'pending' instead of an empty card."""
    runners = [
        {"registration_number": "h1", "horse_name": "A", "program_number": "1"},
        {"registration_number": "h2", "horse_name": "B", "program_number": "2"},
    ]
    with patch("app.api.routes.races.racing_api.get_na_meet_results",
               new=AsyncMock(return_value=_na_meet_results(runners))), \
         patch("app.api.routes.races.asyncio.sleep", new=AsyncMock()):
        r = await client.get("/api/races/results/race/CD_meet-8")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_results_for_race_404_when_positions_zero_or_empty(client):
    runners = [
        {"registration_number": "h1", "horse_name": "A", "official_finish_position": ""},
        {"registration_number": "h2", "horse_name": "B", "official_finish_position": "0"},
        {"registration_number": "h3", "horse_name": "C", "finish_position": ""},
    ]
    with patch("app.api.routes.races.racing_api.get_na_meet_results",
               new=AsyncMock(return_value=_na_meet_results(runners))), \
         patch("app.api.routes.races.asyncio.sleep", new=AsyncMock()):
        r = await client.get("/api/races/results/race/CD_meet-8")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_results_for_race_returns_runners_when_positions_present(client):
    runners = [
        {"registration_number": "h1", "horse_name": "Winner", "official_finish_position": "1", "program_number": "4"},
        {"registration_number": "h2", "horse_name": "Second", "official_finish_position": "2", "program_number": "7"},
        {"registration_number": "h3", "horse_name": "Scratch", "official_finish_position": ""},
    ]
    with patch("app.api.routes.races.racing_api.get_na_meet_results",
               new=AsyncMock(return_value=_na_meet_results(runners))):
        r = await client.get("/api/races/results/race/CD_meet-8")
    assert r.status_code == 200
    body = r.json()
    assert body["race_id"] == "CD_meet-8"
    assert any(rn["position"] == "1" and rn["horse_name"] == "Winner" for rn in body["runners"])
