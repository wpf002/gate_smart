"""
Tests for GET /api/education/* — static content, no mocking needed.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_glossary_returns_200(client):
    r = await client.get("/api/education/glossary")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_glossary_has_terms_key(client):
    body = (await client.get("/api/education/glossary")).json()
    assert "terms" in body
    assert isinstance(body["terms"], list)


@pytest.mark.asyncio
async def test_glossary_has_at_least_25_terms(client):
    body = (await client.get("/api/education/glossary")).json()
    assert len(body["terms"]) >= 25


@pytest.mark.asyncio
async def test_glossary_each_term_has_required_keys(client):
    terms = (await client.get("/api/education/glossary")).json()["terms"]
    for t in terms:
        assert "term" in t, f"Missing 'term' key: {t}"
        assert "definition" in t, f"Missing 'definition' key: {t}"
        assert t["term"], "term must be a non-empty string"
        assert t["definition"], "definition must be a non-empty string"


@pytest.mark.asyncio
async def test_glossary_contains_key_racing_terms(client):
    terms = (await client.get("/api/education/glossary")).json()["terms"]
    names = {t["term"] for t in terms}
    for expected in ("Each Way", "Form", "Going", "Handicap", "SP", "Overlay", "Furlong"):
        assert expected in names, f"'{expected}' missing from glossary"


# ---------------------------------------------------------------------------
# Beginner Guide
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_beginner_guide_returns_200(client):
    r = await client.get("/api/education/beginner-guide")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_beginner_guide_has_sections_and_golden_rules(client):
    body = (await client.get("/api/education/beginner-guide")).json()
    assert "sections" in body
    assert "golden_rules" in body
    assert isinstance(body["sections"], list)
    assert isinstance(body["golden_rules"], list)


@pytest.mark.asyncio
async def test_beginner_guide_has_7_steps(client):
    sections = (await client.get("/api/education/beginner-guide")).json()["sections"]
    assert len(sections) == 7


@pytest.mark.asyncio
async def test_beginner_guide_steps_are_numbered_sequentially(client):
    sections = (await client.get("/api/education/beginner-guide")).json()["sections"]
    for i, s in enumerate(sections, start=1):
        assert s["step"] == i


@pytest.mark.asyncio
async def test_beginner_guide_each_section_has_required_keys(client):
    sections = (await client.get("/api/education/beginner-guide")).json()["sections"]
    for s in sections:
        for key in ("step", "title", "content", "key_point"):
            assert key in s, f"Section missing '{key}': {s}"


@pytest.mark.asyncio
async def test_beginner_guide_has_golden_rules(client):
    rules = (await client.get("/api/education/beginner-guide")).json()["golden_rules"]
    assert len(rules) >= 4
    assert all(isinstance(r, str) and r for r in rules)


# ---------------------------------------------------------------------------
# Bankroll Guide
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bankroll_guide_returns_200(client):
    r = await client.get("/api/education/bankroll-guide")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_bankroll_guide_has_strategies_and_session_rules(client):
    body = (await client.get("/api/education/bankroll-guide")).json()
    assert "strategies" in body
    assert "session_rules" in body


@pytest.mark.asyncio
async def test_bankroll_guide_has_3_strategies(client):
    strategies = (await client.get("/api/education/bankroll-guide")).json()["strategies"]
    assert len(strategies) == 3


@pytest.mark.asyncio
async def test_bankroll_guide_strategy_names(client):
    strategies = (await client.get("/api/education/bankroll-guide")).json()["strategies"]
    names = {s["name"] for s in strategies}
    assert "Flat Staking" in names
    assert "Percentage Staking" in names
    assert "Kelly Criterion" in names


@pytest.mark.asyncio
async def test_bankroll_guide_each_strategy_has_required_keys(client):
    strategies = (await client.get("/api/education/bankroll-guide")).json()["strategies"]
    for s in strategies:
        for key in ("name", "summary", "how_it_works", "pros", "cons", "best_for"):
            assert key in s, f"Strategy missing '{key}': {s['name']}"


@pytest.mark.asyncio
async def test_bankroll_guide_session_rules_are_strings(client):
    rules = (await client.get("/api/education/bankroll-guide")).json()["session_rules"]
    assert len(rules) >= 4
    assert all(isinstance(r, str) and r for r in rules)
