"""
Tests for GET /api/horses/* — racing_api and secretariat are mocked.
Routes now use _find_runner_in_racecards (get_racecards lookup) instead of
get_horse/get_horse_results. Search uses ?q= and the /results route is removed.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

FAKE_RUNNER = {
    "horse_id": "h1",
    "horse": "Arkle",
    "horse_name": "Arkle",
    "age": "7",
    "form": "1-1-1",
}
FAKE_RACECARD_DATA = {
    "racecards": [{
        "race_id": "race1",
        "course": "Cheltenham",
        "time": "14:00",
        "title": "Gold Cup",
        "runners": [FAKE_RUNNER],
    }]
}
EMPTY_RACECARD = {"racecards": []}
FAKE_SEARCH = {"horses": [{"horse_id": "h1", "horse": "Arkle"}], "total": 1}
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
# GET /horses/search?q=
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_search_returns_api_results(client):
    """API path: when search_horses returns results, return them with source=api."""
    mock = AsyncMock(return_value=FAKE_SEARCH)
    with patch("app.api.routes.horses.racing_api.search_horses", new=mock):
        r = await client.get("/api/horses/search?q=Arkle")
    assert r.status_code == 200
    data = r.json()
    assert data["horses"] == FAKE_SEARCH["horses"]
    assert data["source"] == "api"
    mock.assert_called_once_with("Arkle")


@pytest.mark.asyncio
async def test_horse_search_falls_back_to_local(client):
    """When API search returns no horses, fall back to racecard name search."""
    with patch("app.api.routes.horses.racing_api.search_horses",
               new=AsyncMock(return_value={"horses": [], "total": 0})), \
         patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)):
        r = await client.get("/api/horses/search?q=Arkle")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "local"
    assert any(h["horse_name"] == "Arkle" for h in data["horses"])


@pytest.mark.asyncio
async def test_horse_search_falls_back_to_local_on_api_error(client):
    """When API search raises, fall back to racecard search."""
    with patch("app.api.routes.horses.racing_api.search_horses",
               new=AsyncMock(side_effect=Exception("network error"))), \
         patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)):
        r = await client.get("/api/horses/search?q=Arkle")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "local"


@pytest.mark.asyncio
async def test_horse_search_empty_for_short_query(client):
    """Queries shorter than 2 chars return empty without calling APIs."""
    r = await client.get("/api/horses/search?q=A")
    assert r.status_code == 200
    assert r.json() == {"horses": [], "total": 0}


@pytest.mark.asyncio
async def test_horse_search_empty_for_missing_query(client):
    r = await client.get("/api/horses/search")
    assert r.status_code == 200
    assert r.json() == {"horses": [], "total": 0}


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_profile_returns_data(client):
    """Profile is found via racecard runner lookup."""
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)):
        r = await client.get("/api/horses/h1")
    assert r.status_code == 200
    body = r.json()
    assert body["horse_id"] == "h1"
    assert body["horse_name"] == "Arkle"


@pytest.mark.asyncio
async def test_horse_profile_includes_race_context(client):
    """Profile response includes race_context from the parent race."""
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)):
        r = await client.get("/api/horses/h1")
    body = r.json()
    assert "race_context" in body
    assert body["race_context"]["course"] == "Cheltenham"
    assert "runners" not in body["race_context"]


@pytest.mark.asyncio
async def test_horse_profile_404_when_not_in_racecards(client):
    """Returns 404 if the horse_id isn't found in today's or tomorrow's cards."""
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=EMPTY_RACECARD)):
        r = await client.get("/api/horses/unknown")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /horses/{horse_id}/results — route removed (requires Pro plan)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_results_route_removed(client):
    """/results sub-route no longer exists; FastAPI returns 404 or 405."""
    r = await client.get("/api/horses/h1/results")
    assert r.status_code in (404, 405)


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}/explain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_horse_explain_returns_analysis(client):
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
         patch("app.api.routes.horses.secretariat.explain_horse",
               new=AsyncMock(return_value=FAKE_EXPLANATION)):
        r = await client.get("/api/horses/h1/explain")
    assert r.status_code == 200
    body = r.json()
    assert body["horse_id"] == "h1"
    assert body["analysis"] == FAKE_EXPLANATION


@pytest.mark.asyncio
async def test_horse_explain_passes_runner_and_race_context(client):
    """secretariat.explain_horse is called with the runner dict and race context."""
    explain_mock = AsyncMock(return_value=FAKE_EXPLANATION)
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
         patch("app.api.routes.horses.secretariat.explain_horse", new=explain_mock):
        await client.get("/api/horses/h1/explain")
    runner_arg, race_ctx_arg = explain_mock.call_args[0]
    assert runner_arg["horse_id"] == "h1"
    assert race_ctx_arg["course"] == "Cheltenham"


@pytest.mark.asyncio
async def test_horse_explain_404_when_not_found(client):
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=EMPTY_RACECARD)):
        r = await client.get("/api/horses/unknown/explain")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_horse_explain_wraps_secretariat_error(client):
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
         patch("app.api.routes.horses.secretariat.explain_horse",
               new=AsyncMock(side_effect=RuntimeError("claude timeout"))):
        r = await client.get("/api/horses/h1/explain")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# GET /horses/{horse_id}/form/decode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_form_decode_returns_data(client):
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
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
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
         patch("app.api.routes.horses.secretariat.explain_form_string", new=form_mock):
        await client.get("/api/horses/h1/form/decode?form=1-1-F")
    form_mock.assert_called_once_with("1-1-F", "Arkle")


@pytest.mark.asyncio
async def test_form_decode_uses_runner_form_when_no_param(client):
    """When no ?form= param is given, uses the runner's own form string."""
    form_mock = AsyncMock(return_value=FAKE_FORM_DECODE)
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
         patch("app.api.routes.horses.secretariat.explain_form_string", new=form_mock):
        await client.get("/api/horses/h1/form/decode")
    form_mock.assert_called_once_with("1-1-1", "Arkle")  # "1-1-1" from FAKE_RUNNER


@pytest.mark.asyncio
async def test_form_decode_400_when_no_form_available(client):
    """When runner has no form and no ?form= param, returns 400."""
    runner_no_form = {**FAKE_RUNNER, "form": ""}
    racecard_no_form = {
        "racecards": [{"race_id": "race1", "course": "Cheltenham", "runners": [runner_no_form]}]
    }
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=racecard_no_form)):
        r = await client.get("/api/horses/h1/form/decode")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_form_decode_wraps_secretariat_error(client):
    with patch("app.api.routes.horses.racing_api.get_racecards",
               new=AsyncMock(return_value=FAKE_RACECARD_DATA)), \
         patch("app.api.routes.horses.secretariat.explain_form_string",
               new=AsyncMock(side_effect=RuntimeError("timeout"))):
        r = await client.get("/api/horses/h1/form/decode?form=1-1-1")
    assert r.status_code == 502


# ---------------------------------------------------------------------------
# Route ordering — /search must not be captured by /{horse_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_not_captured_by_horse_id_wildcard(client):
    """/horses/search?q=... must hit horse_search(), not horse_profile()."""
    search_mock = AsyncMock(return_value=FAKE_SEARCH)
    racecards_mock = AsyncMock(return_value=EMPTY_RACECARD)
    with patch("app.api.routes.horses.racing_api.search_horses", new=search_mock), \
         patch("app.api.routes.horses.racing_api.get_racecards", new=racecards_mock):
        r = await client.get("/api/horses/search?q=Arkle")
    assert r.status_code == 200
    search_mock.assert_called_once()
    # get_racecards is the profile wildcard path — should NOT be called
    # (API search returned results so no local fallback needed)
    racecards_mock.assert_not_called()
