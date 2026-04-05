"""
Tests for GET /api/races/* — racing_api service is mocked throughout.
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

FAKE_RACECARDS = {"racecards": [{"race_id": "r1", "course": "Cheltenham"}]}
FAKE_RACE = {"race_id": "r1", "course": "Cheltenham", "runners": []}
FAKE_RESULTS = {"results": [{"race_id": "r1", "winner": "Arkle"}]}


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
    with patch("app.api.routes.races.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARDS)):
        r = await client.get("/api/races/today?region=gb")
    assert r.status_code == 200
    assert r.json() == FAKE_RACECARDS


@pytest.mark.asyncio
async def test_races_today_passes_region(client):
    mock = AsyncMock(return_value=FAKE_RACECARDS)
    with patch("app.api.routes.races.racing_api.get_racecards", new=mock):
        await client.get("/api/races/today?region=ire")
    mock.assert_called_once_with(region="ire")


@pytest.mark.asyncio
async def test_races_today_defaults_region_to_none(client):
    mock = AsyncMock(return_value=FAKE_RACECARDS)
    with patch("app.api.routes.races.racing_api.get_racecards", new=mock):
        await client.get("/api/races/today")
    mock.assert_called_once_with(region=None)


@pytest.mark.asyncio
async def test_races_today_propagates_502(client):
    with patch("app.api.routes.races.racing_api.get_racecards",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 401"))):
        r = await client.get("/api/races/today")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_races_today_wraps_unexpected_errors(client):
    with patch("app.api.routes.races.racing_api.get_racecards",
               new=AsyncMock(side_effect=RuntimeError("connection reset"))):
        r = await client.get("/api/races/today")
    assert r.status_code == 502
    assert "Racing API error" in r.json()["detail"]


# ---------------------------------------------------------------------------
# GET /races/date/{race_date}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_races_by_date(client):
    mock = AsyncMock(return_value=FAKE_RACECARDS)
    with patch("app.api.routes.races.racing_api.get_racecards", new=mock):
        r = await client.get("/api/races/date/2026-04-05?region=gb")
    assert r.status_code == 200
    mock.assert_called_once_with(date="2026-04-05", region="gb")


# ---------------------------------------------------------------------------
# GET /races/results/today
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_today(client):
    mock = AsyncMock(return_value=FAKE_RESULTS)
    with patch("app.api.routes.races.racing_api.get_results", new=mock):
        r = await client.get("/api/races/results/today?region=gb")
    assert r.status_code == 200
    assert r.json() == FAKE_RESULTS
    mock.assert_called_once_with(region="gb")


# ---------------------------------------------------------------------------
# GET /races/results/{result_date}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_by_date(client):
    mock = AsyncMock(return_value=FAKE_RESULTS)
    with patch("app.api.routes.races.racing_api.get_results", new=mock):
        r = await client.get("/api/races/results/2026-04-05?region=ire")
    assert r.status_code == 200
    mock.assert_called_once_with(date="2026-04-05", region="ire")


# ---------------------------------------------------------------------------
# GET /races/{race_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_race_detail(client):
    mock = AsyncMock(return_value=FAKE_RACE)
    with patch("app.api.routes.races.racing_api.get_race", new=mock):
        r = await client.get("/api/races/race-123")
    assert r.status_code == 200
    assert r.json() == FAKE_RACE
    mock.assert_called_once_with("race-123")


@pytest.mark.asyncio
async def test_race_detail_propagates_502(client):
    with patch("app.api.routes.races.racing_api.get_race",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 404"))):
        r = await client.get("/api/races/unknown-race")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# Route ordering — literal paths must not be captured by /{race_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_results_today_not_captured_by_race_id_wildcard(client):
    """GET /races/results/today must hit results_today(), not race_detail()."""
    results_mock = AsyncMock(return_value=FAKE_RESULTS)
    race_mock = AsyncMock(return_value=FAKE_RACE)
    with patch("app.api.routes.races.racing_api.get_results", new=results_mock), \
         patch("app.api.routes.races.racing_api.get_race", new=race_mock):
        await client.get("/api/races/results/today")
    results_mock.assert_called_once()
    race_mock.assert_not_called()
