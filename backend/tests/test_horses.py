"""
Tests for GET /api/horses/* — racing_api and secretariat are mocked.
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

FAKE_HORSE = {"horse_id": "h1", "horse": "Arkle", "age": "7", "form": "1-1-1"}
FAKE_RESULTS = {"results": [{"position": 1, "race": "Gold Cup"}]}
FAKE_SEARCH = {"horses": [{"horse_id": "h1", "horse": "Arkle"}]}
FAKE_EXPLANATION = {
    "form_summary": "Brilliant recent form",
    "key_stats": ["3 wins from 3"],
    "strengths": ["Jumps well"],
    "concerns": [],
    "verdict": "Outstanding",
    "good_for_beginners": True,
    "beginner_explanation": "This horse wins a lot.",
}
FAKE_FORM_DECODE = {
    "decoded": [{"result": "1", "meaning": "Won"}],
    "plain_english": "All wins",
    "trend": "consistent",
    "red_flags": [],
    "positive_signs": ["Always wins"],
}


@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /horses/search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_search_returns_data(client):
    mock = AsyncMock(return_value=FAKE_SEARCH)
    with patch("app.api.routes.horses.racing_api.search_horses", new=mock):
        r = await client.get("/api/horses/search?name=Arkle")
    assert r.status_code == 200
    assert r.json() == FAKE_SEARCH
    mock.assert_called_once_with("Arkle")


@pytest.mark.asyncio
async def test_horse_search_propagates_502(client):
    with patch("app.api.routes.horses.racing_api.search_horses",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 401"))):
        r = await client.get("/api/horses/search?name=x")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_profile_returns_data(client):
    mock = AsyncMock(return_value=FAKE_HORSE)
    with patch("app.api.routes.horses.racing_api.get_horse", new=mock):
        r = await client.get("/api/horses/h1")
    assert r.status_code == 200
    assert r.json() == FAKE_HORSE
    mock.assert_called_once_with("h1")


@pytest.mark.asyncio
async def test_horse_profile_propagates_502(client):
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 404"))):
        r = await client.get("/api/horses/unknown")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}/results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_results_returns_data(client):
    mock = AsyncMock(return_value=FAKE_RESULTS)
    with patch("app.api.routes.horses.racing_api.get_horse_results", new=mock):
        r = await client.get("/api/horses/h1/results")
    assert r.status_code == 200
    assert r.json() == FAKE_RESULTS
    mock.assert_called_once_with("h1", limit=10)


@pytest.mark.asyncio
async def test_horse_results_respects_limit_param(client):
    mock = AsyncMock(return_value=FAKE_RESULTS)
    with patch("app.api.routes.horses.racing_api.get_horse_results", new=mock):
        await client.get("/api/horses/h1/results?limit=5")
    mock.assert_called_once_with("h1", limit=5)


@pytest.mark.asyncio
async def test_horse_results_propagates_502(client):
    with patch("app.api.routes.horses.racing_api.get_horse_results",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 500"))):
        r = await client.get("/api/horses/h1/results")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}/explain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_explain_returns_analysis(client):
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(return_value=dict(FAKE_HORSE))), \
         patch("app.api.routes.horses.racing_api.get_horse_results",
               new=AsyncMock(return_value=FAKE_RESULTS)), \
         patch("app.api.routes.horses.secretariat.explain_horse",
               new=AsyncMock(return_value=FAKE_EXPLANATION)):
        r = await client.get("/api/horses/h1/explain")
    assert r.status_code == 200
    body = r.json()
    assert body["horse_id"] == "h1"
    assert body["analysis"] == FAKE_EXPLANATION


@pytest.mark.asyncio
async def test_horse_explain_merges_results_into_horse_data(client):
    """explain_horse() must be called with recent_results attached."""
    horse_data = dict(FAKE_HORSE)
    explain_mock = AsyncMock(return_value=FAKE_EXPLANATION)
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(return_value=horse_data)), \
         patch("app.api.routes.horses.racing_api.get_horse_results",
               new=AsyncMock(return_value=FAKE_RESULTS)), \
         patch("app.api.routes.horses.secretariat.explain_horse", new=explain_mock):
        await client.get("/api/horses/h1/explain")
    called_with = explain_mock.call_args[0][0]
    assert "recent_results" in called_with
    assert called_with["recent_results"] == FAKE_RESULTS


@pytest.mark.asyncio
async def test_horse_explain_propagates_racing_api_502(client):
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 404"))):
        r = await client.get("/api/horses/h1/explain")
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_horse_explain_wraps_secretariat_error(client):
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(return_value=dict(FAKE_HORSE))), \
         patch("app.api.routes.horses.racing_api.get_horse_results",
               new=AsyncMock(return_value=FAKE_RESULTS)), \
         patch("app.api.routes.horses.secretariat.explain_horse",
               new=AsyncMock(side_effect=RuntimeError("claude timeout"))):
        r = await client.get("/api/horses/h1/explain")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}/form/decode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_form_decode_returns_data(client):
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(return_value=FAKE_HORSE)), \
         patch("app.api.routes.horses.secretariat.explain_form_string",
               new=AsyncMock(return_value=FAKE_FORM_DECODE)):
        r = await client.get("/api/horses/h1/form/decode?form=1-1-1")
    assert r.status_code == 200
    body = r.json()
    assert body["horse_id"] == "h1"
    assert body["form"] == "1-1-1"
    assert body["decoded"] == FAKE_FORM_DECODE


@pytest.mark.asyncio
async def test_form_decode_passes_horse_name_to_secretariat(client):
    form_mock = AsyncMock(return_value=FAKE_FORM_DECODE)
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(return_value=FAKE_HORSE)), \
         patch("app.api.routes.horses.secretariat.explain_form_string", new=form_mock):
        await client.get("/api/horses/h1/form/decode?form=1-1-F")
    form_mock.assert_called_once_with("1-1-F", "Arkle")


@pytest.mark.asyncio
async def test_form_decode_falls_back_to_horse_id_if_no_name(client):
    form_mock = AsyncMock(return_value=FAKE_FORM_DECODE)
    with patch("app.api.routes.horses.racing_api.get_horse",
               new=AsyncMock(return_value={"horse_id": "h1"})), \
         patch("app.api.routes.horses.secretariat.explain_form_string", new=form_mock):
        await client.get("/api/horses/h1/form/decode?form=1-2")
    form_mock.assert_called_once_with("1-2", "h1")


# ---------------------------------------------------------------------------
# Route ordering — /search must not be captured by /{horse_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_not_captured_by_horse_id_wildcard(client):
    search_mock = AsyncMock(return_value=FAKE_SEARCH)
    profile_mock = AsyncMock(return_value=FAKE_HORSE)
    with patch("app.api.routes.horses.racing_api.search_horses", new=search_mock), \
         patch("app.api.routes.horses.racing_api.get_horse", new=profile_mock):
        await client.get("/api/horses/search?name=Arkle")
    search_mock.assert_called_once()
    profile_mock.assert_not_called()
