"""
Tests for the betting routes and helper functions.

Pure Python logic — no external calls, no mocking needed.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.routes.betting import (
    _american_to_decimal,
    _decimal_to_american,
    _decimal_to_fractional,
    _fractional_to_decimal,
    _parse_odds,
)


@pytest_asyncio.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Unit tests — helper functions
# ---------------------------------------------------------------------------

class TestFractionalToDecimal:
    def test_5_2(self):
        assert _fractional_to_decimal("5/2") == pytest.approx(3.5)

    def test_evens(self):
        assert _fractional_to_decimal("1/1") == pytest.approx(2.0)

    def test_short_price(self):
        assert _fractional_to_decimal("1/4") == pytest.approx(1.25)

    def test_long_shot(self):
        assert _fractional_to_decimal("33/1") == pytest.approx(34.0)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _fractional_to_decimal("notodds")


class TestDecimalToFractional:
    def test_3_5_snaps_to_5_2(self):
        assert _decimal_to_fractional(3.5) == "5/2"

    def test_evens(self):
        assert _decimal_to_fractional(2.0) == "1/1"

    def test_short_price(self):
        assert _decimal_to_fractional(1.25) == "1/4"

    def test_longshot(self):
        assert _decimal_to_fractional(34.0) == "33/1"


class TestAmericanToDecimal:
    def test_plus_250(self):
        assert _american_to_decimal(250) == pytest.approx(3.5)

    def test_minus_200(self):
        assert _american_to_decimal(-200) == pytest.approx(1.5)

    def test_plus_100_evens(self):
        assert _american_to_decimal(100) == pytest.approx(2.0)

    def test_minus_100_evens(self):
        assert _american_to_decimal(-100) == pytest.approx(2.0)

    def test_plus_500(self):
        assert _american_to_decimal(500) == pytest.approx(6.0)


class TestDecimalToAmerican:
    def test_3_5_to_plus_250(self):
        assert _decimal_to_american(3.5) == 250

    def test_1_5_to_minus_200(self):
        assert _decimal_to_american(1.5) == -200

    def test_evens(self):
        assert _decimal_to_american(2.0) == 100


class TestParseOdds:
    def test_fractional(self):
        assert _parse_odds("5/2") == pytest.approx(3.5)

    def test_decimal_string(self):
        assert _parse_odds("3.5") == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# GET /betting/types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bet_types_returns_200(client):
    r = await client.get("/api/betting/types")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_bet_types_has_single_and_exotic_keys(client):
    body = (await client.get("/api/betting/types")).json()
    assert "single_bets" in body
    assert "exotic_bets" in body


@pytest.mark.asyncio
async def test_bet_types_single_bets_count(client):
    body = (await client.get("/api/betting/types")).json()
    assert len(body["single_bets"]) == 4


@pytest.mark.asyncio
async def test_bet_types_exotic_bets_count(client):
    body = (await client.get("/api/betting/types")).json()
    assert len(body["exotic_bets"]) == 9


@pytest.mark.asyncio
async def test_bet_types_required_keys_present(client):
    body = (await client.get("/api/betting/types")).json()
    for bet in body["single_bets"] + body["exotic_bets"]:
        assert "type" in bet
        assert "description" in bet
        assert "risk" in bet
        assert "best_for" in bet


@pytest.mark.asyncio
async def test_bet_types_contains_expected_single_bets(client):
    names = {b["type"] for b in (await client.get("/api/betting/types")).json()["single_bets"]}
    assert names == {"Win", "Place", "Show", "Each Way"}


@pytest.mark.asyncio
async def test_bet_types_contains_expected_exotic_types(client):
    names = {b["type"] for b in (await client.get("/api/betting/types")).json()["exotic_bets"]}
    for expected in ("Exacta", "Quinella", "Trifecta", "Superfecta", "Daily Double", "Pick 6"):
        assert expected in names


# ---------------------------------------------------------------------------
# POST /betting/odds/convert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_convert_fractional_5_2(client):
    r = await client.post("/api/betting/odds/convert", json={"fractional": "5/2", "stake": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["decimal"] == pytest.approx(3.5, rel=1e-3)
    assert body["american"] == 250
    assert body["fractional"] == "5/2"
    assert body["implied_probability"] == pytest.approx(28.57, rel=1e-2)
    assert body["profit_on_stake"] == pytest.approx(25.0)
    assert body["total_return"] == pytest.approx(35.0)
    assert body["stake"] == 10.0


@pytest.mark.asyncio
async def test_convert_decimal_input(client):
    r = await client.post("/api/betting/odds/convert", json={"decimal": 3.5, "stake": 20})
    assert r.status_code == 200
    body = r.json()
    assert body["fractional"] == "5/2"
    assert body["total_return"] == pytest.approx(70.0)


@pytest.mark.asyncio
async def test_convert_american_positive(client):
    r = await client.post("/api/betting/odds/convert", json={"american": 250, "stake": 10})
    assert r.status_code == 200
    assert r.json()["decimal"] == pytest.approx(3.5, rel=1e-3)


@pytest.mark.asyncio
async def test_convert_american_negative(client):
    r = await client.post("/api/betting/odds/convert", json={"american": -200, "stake": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["decimal"] == pytest.approx(1.5, rel=1e-3)
    assert body["total_return"] == pytest.approx(15.0)


@pytest.mark.asyncio
async def test_convert_default_stake_is_10(client):
    r = await client.post("/api/betting/odds/convert", json={"fractional": "1/1"})
    assert r.status_code == 200
    assert r.json()["stake"] == 10.0


@pytest.mark.asyncio
async def test_convert_no_odds_returns_400(client):
    r = await client.post("/api/betting/odds/convert", json={"stake": 10})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_convert_invalid_fractional_returns_400(client):
    r = await client.post("/api/betting/odds/convert", json={"fractional": "notodds"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_convert_decimal_lte_1_returns_400(client):
    r = await client.post("/api/betting/odds/convert", json={"decimal": 1.0})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /betting/payout/calculate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_payout_win(client):
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "win", "stake": 10, "odds": ["5/1"]})
    assert r.status_code == 200
    body = r.json()
    assert body["estimated_return"] == pytest.approx(60.0)
    assert body["estimated_profit"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_payout_place(client):
    # 5/1 → decimal 6.0, place_dec = (6-1)/4 + 1 = 2.25
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "place", "stake": 10, "odds": ["5/1"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(22.5)


@pytest.mark.asyncio
async def test_payout_show(client):
    # 5/1 → decimal 6.0, show_dec = (6-1)/5 + 1 = 2.0
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "show", "stake": 10, "odds": ["5/1"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_payout_exacta(client):
    # 5/2 × 3/1 = 3.5 × 4.0 = 14.0, × 0.80 = 11.2, × 10 = 112.0
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "exacta", "stake": 10, "odds": ["5/2", "3/1"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(112.0)


@pytest.mark.asyncio
async def test_payout_trifecta(client):
    # 5/1 × 3/1 × 7/2 = 6.0 × 4.0 × 4.5 = 108.0, × 0.75 = 81.0, × 10 = 810.0
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "trifecta", "stake": 10, "odds": ["5/1", "3/1", "7/2"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(810.0)


@pytest.mark.asyncio
async def test_payout_superfecta(client):
    # 5/1 × 3/1 × 7/2 × 2/1 = 6×4×4.5×3 = 324.0, × 0.70 = 226.8, × 10 = 2268.0
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "superfecta", "stake": 10,
                                "odds": ["5/1", "3/1", "7/2", "2/1"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(2268.0)


@pytest.mark.asyncio
async def test_payout_each_way(client):
    # 10/1 → dec 11.0, place_dec = (11-1)/4 + 1 = 3.5
    # £5 win @ 11 + £5 place @ 3.5 = 55 + 17.5 = 72.5
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "each_way", "stake": 10, "odds": ["10/1"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(72.5)


@pytest.mark.asyncio
async def test_payout_each_way_via_flag(client):
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "win", "stake": 10, "odds": ["10/1"], "each_way": True})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(72.5)


@pytest.mark.asyncio
async def test_payout_missing_odds_returns_400(client):
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "win", "stake": 10, "odds": []})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_payout_response_has_required_keys(client):
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "win", "stake": 10, "odds": ["2/1"]})
    body = r.json()
    for key in ("bet_type", "stake", "estimated_return", "estimated_profit", "note"):
        assert key in body


@pytest.mark.asyncio
async def test_payout_profit_equals_return_minus_stake(client):
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "win", "stake": 15, "odds": ["3/1"]})
    body = r.json()
    assert body["estimated_profit"] == pytest.approx(body["estimated_return"] - body["stake"])


@pytest.mark.asyncio
async def test_payout_quinella_same_factor_as_exacta(client):
    payload = {"stake": 10, "odds": ["5/2", "3/1"]}
    exacta = (await client.post("/api/betting/payout/calculate",
                                json={"bet_type": "exacta", **payload})).json()
    quinella = (await client.post("/api/betting/payout/calculate",
                                  json={"bet_type": "quinella", **payload})).json()
    assert exacta["estimated_return"] == pytest.approx(quinella["estimated_return"])


@pytest.mark.asyncio
async def test_payout_unknown_bet_type_treated_as_win(client):
    r = await client.post("/api/betting/payout/calculate",
                          json={"bet_type": "custom_exotic", "stake": 10, "odds": ["5/1"]})
    assert r.status_code == 200
    assert r.json()["estimated_return"] == pytest.approx(60.0)
