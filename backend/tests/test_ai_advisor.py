"""
Tests for POST /api/advisor/* — racing_api, secretariat, and cache are mocked.

ai_advisor.py imports:
  from app.core.cache import cache_get, cache_set      → patch these names on the module
  from app.services import racing_api, secretariat     → patch methods on those module refs
"""
import json
import pytest
import pytest_asyncio
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

FAKE_RACE = {"race_id": "race-1", "course": "Cheltenham", "runners": []}
FAKE_ANALYSIS = {
    "race_summary": "Competitive field",
    "pace_scenario": "Strong pace expected",
    "track_bias_notes": "None",
    "vulnerable_favorite": None,
    "runners": [],
    "top_contenders": ["Arkle"],
    "longshot_alert": {"horse_name": None, "reason": "", "odds": ""},
    "recommended_bets": [],
    "overall_summary": "Go with the form horse",
    "confidence": "high",
    "beginner_tip": "Bet the favourite",
}
FAKE_FORM_DECODE = {
    "decoded": [{"result": "1", "meaning": "Won"}],
    "plain_english": "All wins recently",
    "trend": "consistent",
    "red_flags": [],
    "positive_signs": ["Always wins"],
}
FAKE_RECOMMENDATION = {
    "primary_bet": {"type": "Win", "selection": "Arkle", "stake": 10.0,
                    "reasoning": "Best form", "expected_value": "positive", "payout_if_wins": "$60"},
    "alternative_bet": {"type": "Place", "selection": "Arkle", "stake": 5.0,
                        "reasoning": "Safer", "payout_if_wins": "$15"},
    "bankroll_advice": "Stake 2%",
    "bet_sizing_explanation": "Safe amount",
}


@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _body(data: dict) -> bytes:
    return json.dumps(data).encode()


# ---------------------------------------------------------------------------
# POST /advisor/analyze — cache miss path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_returns_analysis_on_cache_miss(client):
    with patch("app.api.routes.ai_advisor.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.api.routes.ai_advisor.cache_set", new=AsyncMock()), \
         patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race",
               new=AsyncMock(return_value=FAKE_ANALYSIS)):
        r = await client.post("/api/advisor/analyze",
                              content=_body({"race_id": "race-1", "mode": "balanced"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == FAKE_ANALYSIS


@pytest.mark.asyncio
async def test_analyze_calls_secretariat_with_mode_and_bankroll(client):
    analyze_mock = AsyncMock(return_value=FAKE_ANALYSIS)
    with patch("app.api.routes.ai_advisor.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.api.routes.ai_advisor.cache_set", new=AsyncMock()), \
         patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race", new=analyze_mock):
        await client.post("/api/advisor/analyze",
                          content=_body({"race_id": "r1", "mode": "aggressive", "bankroll": 500.0}),
                          headers={"Content-Type": "application/json"})
    analyze_mock.assert_called_once_with(FAKE_RACE, mode="aggressive", bankroll=500.0)


@pytest.mark.asyncio
async def test_analyze_stores_result_in_cache(client):
    cache_set_mock = AsyncMock()
    with patch("app.api.routes.ai_advisor.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.api.routes.ai_advisor.cache_set", new=cache_set_mock), \
         patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race",
               new=AsyncMock(return_value=FAKE_ANALYSIS)):
        await client.post("/api/advisor/analyze",
                          content=_body({"race_id": "race-1", "mode": "balanced"}),
                          headers={"Content-Type": "application/json"})
    cache_set_mock.assert_called_once_with("ai_analysis:race-1:balanced", FAKE_ANALYSIS, ex=300)


# ---------------------------------------------------------------------------
# POST /advisor/analyze — cache hit path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_returns_cached_result_without_calling_api(client):
    race_mock = AsyncMock(return_value=FAKE_RACE)
    secretariat_mock = AsyncMock(return_value=FAKE_ANALYSIS)
    with patch("app.api.routes.ai_advisor.cache_get", new=AsyncMock(return_value=FAKE_ANALYSIS)), \
         patch("app.api.routes.ai_advisor.racing_api.get_race", new=race_mock), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race", new=secretariat_mock):
        r = await client.post("/api/advisor/analyze",
                              content=_body({"race_id": "race-1"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == FAKE_ANALYSIS
    race_mock.assert_not_called()
    secretariat_mock.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_cache_key_includes_race_id_and_mode(client):
    cache_get_mock = AsyncMock(return_value=FAKE_ANALYSIS)
    with patch("app.api.routes.ai_advisor.cache_get", new=cache_get_mock), \
         patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)):
        await client.post("/api/advisor/analyze",
                          content=_body({"race_id": "race-99", "mode": "longshot"}),
                          headers={"Content-Type": "application/json"})
    cache_get_mock.assert_called_once_with("ai_analysis:race-99:longshot")


# ---------------------------------------------------------------------------
# POST /advisor/analyze — error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_400_on_bad_body(client):
    r = await client.post("/api/advisor/analyze",
                          content=b"not json",
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_analyze_400_on_missing_race_id(client):
    r = await client.post("/api/advisor/analyze",
                          content=_body({"mode": "balanced"}),
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_analyze_propagates_racing_api_502(client):
    with patch("app.api.routes.ai_advisor.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(side_effect=HTTPException(502, "Racing API error: 401"))):
        r = await client.post("/api/advisor/analyze",
                              content=_body({"race_id": "r1"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_analyze_wraps_secretariat_error_as_502(client):
    with patch("app.api.routes.ai_advisor.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.api.routes.ai_advisor.cache_set", new=AsyncMock()), \
         patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race",
               new=AsyncMock(side_effect=RuntimeError("claude timeout"))):
        r = await client.post("/api/advisor/analyze",
                              content=_body({"race_id": "r1"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 502
    assert "AI analysis error" in r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /advisor/recommend-bet
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recommend_bet_returns_recommendation(client):
    with patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race",
               new=AsyncMock(return_value=FAKE_ANALYSIS)), \
         patch("app.api.routes.ai_advisor.secretariat.recommend_bet_type",
               new=AsyncMock(return_value=FAKE_RECOMMENDATION)):
        r = await client.post("/api/advisor/recommend-bet",
                              content=_body({"race_id": "r1", "bankroll": 500.0,
                                             "risk_tolerance": "medium",
                                             "experience_level": "intermediate"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == FAKE_RECOMMENDATION


@pytest.mark.asyncio
async def test_recommend_bet_uses_balanced_mode_for_analysis(client):
    analyze_mock = AsyncMock(return_value=FAKE_ANALYSIS)
    with patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race", new=analyze_mock), \
         patch("app.api.routes.ai_advisor.secretariat.recommend_bet_type",
               new=AsyncMock(return_value=FAKE_RECOMMENDATION)):
        await client.post("/api/advisor/recommend-bet",
                          content=_body({"race_id": "r1", "bankroll": 100.0}),
                          headers={"Content-Type": "application/json"})
    analyze_mock.assert_called_once_with(FAKE_RACE, mode="balanced")


@pytest.mark.asyncio
async def test_recommend_bet_passes_profile_to_secretariat(client):
    rec_mock = AsyncMock(return_value=FAKE_RECOMMENDATION)
    with patch("app.api.routes.ai_advisor.racing_api.get_race",
               new=AsyncMock(return_value=FAKE_RACE)), \
         patch("app.api.routes.ai_advisor.secretariat.analyze_race",
               new=AsyncMock(return_value=FAKE_ANALYSIS)), \
         patch("app.api.routes.ai_advisor.secretariat.recommend_bet_type", new=rec_mock):
        await client.post("/api/advisor/recommend-bet",
                          content=_body({"race_id": "r1", "bankroll": 250.0,
                                         "risk_tolerance": "aggressive",
                                         "experience_level": "expert"}),
                          headers={"Content-Type": "application/json"})
    rec_mock.assert_called_once_with(250.0, "aggressive", "expert", FAKE_ANALYSIS)


@pytest.mark.asyncio
async def test_recommend_bet_400_on_bad_body(client):
    r = await client.post("/api/advisor/recommend-bet",
                          content=b"garbage",
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_recommend_bet_400_on_missing_bankroll(client):
    r = await client.post("/api/advisor/recommend-bet",
                          content=_body({"race_id": "r1"}),
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /advisor/ask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ask_returns_answer(client):
    with patch("app.api.routes.ai_advisor.secretariat.answer_betting_question",
               new=AsyncMock(return_value="An each way bet is two bets in one.")):
        r = await client.post("/api/advisor/ask",
                              content=_body({"question": "What is each way?"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == {"answer": "An each way bet is two bets in one."}


@pytest.mark.asyncio
async def test_ask_passes_question_and_context(client):
    ask_mock = AsyncMock(return_value="Answer")
    ctx = {"race_id": "r1", "horse": "Arkle"}
    with patch("app.api.routes.ai_advisor.secretariat.answer_betting_question", new=ask_mock):
        await client.post("/api/advisor/ask",
                          content=_body({"question": "Is this horse value?", "context": ctx}),
                          headers={"Content-Type": "application/json"})
    ask_mock.assert_called_once_with("Is this horse value?", ctx)


@pytest.mark.asyncio
async def test_ask_context_defaults_to_none(client):
    ask_mock = AsyncMock(return_value="Answer")
    with patch("app.api.routes.ai_advisor.secretariat.answer_betting_question", new=ask_mock):
        await client.post("/api/advisor/ask",
                          content=_body({"question": "What is a furlong?"}),
                          headers={"Content-Type": "application/json"})
    ask_mock.assert_called_once_with("What is a furlong?", None)


@pytest.mark.asyncio
async def test_ask_400_on_bad_body(client):
    r = await client.post("/api/advisor/ask",
                          content=b"{}",
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ask_502_on_secretariat_error(client):
    with patch("app.api.routes.ai_advisor.secretariat.answer_betting_question",
               new=AsyncMock(side_effect=RuntimeError("timeout"))):
        r = await client.post("/api/advisor/ask",
                              content=_body({"question": "help"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 502
    assert "AI error" in r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /advisor/explain-form
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_form_returns_decoded_result(client):
    with patch("app.api.routes.ai_advisor.secretariat.explain_form_string",
               new=AsyncMock(return_value=FAKE_FORM_DECODE)):
        r = await client.post("/api/advisor/explain-form",
                              content=_body({"form_string": "1-1-2", "horse_name": "Arkle"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == FAKE_FORM_DECODE


@pytest.mark.asyncio
async def test_explain_form_passes_form_and_name_to_secretariat(client):
    mock = AsyncMock(return_value=FAKE_FORM_DECODE)
    with patch("app.api.routes.ai_advisor.secretariat.explain_form_string", new=mock):
        await client.post("/api/advisor/explain-form",
                          content=_body({"form_string": "1-F-2", "horse_name": "Desert Orchid"}),
                          headers={"Content-Type": "application/json"})
    mock.assert_called_once_with("1-F-2", "Desert Orchid")


@pytest.mark.asyncio
async def test_explain_form_uses_form_string_as_name_when_name_omitted(client):
    mock = AsyncMock(return_value=FAKE_FORM_DECODE)
    with patch("app.api.routes.ai_advisor.secretariat.explain_form_string", new=mock):
        await client.post("/api/advisor/explain-form",
                          content=_body({"form_string": "1-2-3"}),
                          headers={"Content-Type": "application/json"})
    mock.assert_called_once_with("1-2-3", "1-2-3")


@pytest.mark.asyncio
async def test_explain_form_400_on_empty_form_string(client):
    r = await client.post("/api/advisor/explain-form",
                          content=_body({"form_string": "", "horse_name": "Arkle"}),
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_explain_form_400_on_bad_body(client):
    r = await client.post("/api/advisor/explain-form",
                          content=b"not json",
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_explain_form_502_on_secretariat_error(client):
    with patch("app.api.routes.ai_advisor.secretariat.explain_form_string",
               new=AsyncMock(side_effect=RuntimeError("claude timeout"))):
        r = await client.post("/api/advisor/explain-form",
                              content=_body({"form_string": "1-1-1", "horse_name": "Arkle"}),
                              headers={"Content-Type": "application/json"})
    assert r.status_code == 502
    assert "AI error" in r.json()["detail"]
