"""
Tests for the TrackSense integration layer.

Uses in-memory dicts to stand in for Redis — no real Redis instance required.
Run with:  pytest backend/tests/ -v
"""
import hashlib
import hmac
import json
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EPC = "E2004700000000000000001A"
HORSE_ID = "test-001"
HORSE_NAME = "Test Horse"
SECRET = "testsecret"

SECTIONAL_PAYLOAD = {
    "race_id": "race-001",
    "venue": "Cheltenham",
    "race_name": "Gold Cup Trial",
    "distance_furlongs": 16.0,
    "completed_at": "2026-04-04T14:30:00Z",
    "results": [
        {
            "finish_position": 1,
            "epc": EPC,
            "horse_name": HORSE_NAME,
            "total_time_ms": 198400,
            "sectionals": [
                {"gate_name": "2f",     "gate_distance_furlongs": 2.0, "split_time_ms": 24800, "speed_kmh": 58.2},
                {"gate_name": "4f",     "gate_distance_furlongs": 2.0, "split_time_ms": 23900, "speed_kmh": 60.4},
                {"gate_name": "6f",     "gate_distance_furlongs": 2.0, "split_time_ms": 24100, "speed_kmh": 59.8},
                {"gate_name": "finish", "gate_distance_furlongs": 2.0, "split_time_ms": 23600, "speed_kmh": 61.1},
            ],
        }
    ],
}


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_cache(store: dict):
    """Return cache_get / cache_set backed by a plain dict."""
    async def _get(key):
        val = store.get(key)
        return json.loads(val) if val is not None else None

    async def _set(key, value, ex=None):
        store[key] = json.dumps(value)

    return _get, _set


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client_no_secret():
    """HTTP client with no webhook secret (dev bypass active)."""
    store = {}
    _get, _set = _make_fake_cache(store)

    # Must patch the names as they exist in the tracksense module (imported at
    # top level with `from app.core.cache import cache_get, cache_set`).
    with patch("app.api.routes.tracksense.cache_get", new=_get), \
         patch("app.api.routes.tracksense.cache_set", new=_set), \
         patch("app.api.routes.tracksense.settings.TRACKSENSE_WEBHOOK_SECRET", ""):
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac, store


@pytest_asyncio.fixture
async def client_with_secret():
    """HTTP client with HMAC secret enforced."""
    store = {}
    _get, _set = _make_fake_cache(store)

    with patch("app.api.routes.tracksense.cache_get", new=_get), \
         patch("app.api.routes.tracksense.cache_set", new=_set), \
         patch("app.api.routes.tracksense.settings.TRACKSENSE_WEBHOOK_SECRET", SECRET):
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac, store


# ---------------------------------------------------------------------------
# Part 1 — Horse identity mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_map_horse_returns_correct_fields(client_no_secret):
    ac, _ = client_no_secret
    r = await ac.post("/api/tracksense/map", json={
        "racing_api_horse_id": HORSE_ID, "epc": EPC, "horse_name": HORSE_NAME,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["stored"] is True
    assert body["racing_api_horse_id"] == HORSE_ID
    assert body["epc"] == EPC


@pytest.mark.asyncio
async def test_map_horse_persists_to_redis(client_no_secret):
    ac, store = client_no_secret
    await ac.post("/api/tracksense/map", json={
        "racing_api_horse_id": HORSE_ID, "epc": EPC, "horse_name": HORSE_NAME,
    })
    saved = json.loads(store[f"tracksense:map:{HORSE_ID}"])
    assert saved["epc"] == EPC
    assert saved["horse_name"] == HORSE_NAME
    assert "mapped_at" in saved


@pytest.mark.asyncio
async def test_get_mapping_returns_stored_data(client_no_secret):
    ac, _ = client_no_secret
    await ac.post("/api/tracksense/map", json={
        "racing_api_horse_id": HORSE_ID, "epc": EPC, "horse_name": HORSE_NAME,
    })
    r = await ac.get(f"/api/tracksense/map/{HORSE_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["epc"] == EPC
    assert body["horse_name"] == HORSE_NAME
    assert "mapped_at" in body


@pytest.mark.asyncio
async def test_get_mapping_404_for_unknown_id(client_no_secret):
    ac, _ = client_no_secret
    r = await ac.get("/api/tracksense/map/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_map_horse_bad_body_returns_400(client_no_secret):
    ac, _ = client_no_secret
    r = await ac.post(
        "/api/tracksense/map",
        content=b"not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Part 2 — Webhook: dev bypass (no secret)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_accepted_without_secret(client_no_secret):
    ac, _ = client_no_secret
    r = await ac.post("/api/tracksense/webhook", json=SECTIONAL_PAYLOAD)
    assert r.status_code == 200
    assert r.json() == {"accepted": True, "horses_stored": 1}


@pytest.mark.asyncio
async def test_webhook_stores_sectionals_in_redis(client_no_secret):
    ac, store = client_no_secret
    await ac.post("/api/tracksense/webhook", json=SECTIONAL_PAYLOAD)

    key = f"tracksense:sectionals:{EPC}"
    assert key in store
    history = json.loads(store[key])
    assert len(history) == 1
    entry = history[0]
    assert entry["race_id"] == "race-001"
    assert entry["venue"] == "Cheltenham"
    assert entry["finish_position"] == 1
    assert len(entry["sectionals"]) == 4
    assert entry["sectionals"][0]["gate_name"] == "2f"
    assert entry["sectionals"][0]["speed_kmh"] == 58.2


@pytest.mark.asyncio
async def test_webhook_appends_on_subsequent_calls(client_no_secret):
    ac, store = client_no_secret
    await ac.post("/api/tracksense/webhook", json=SECTIONAL_PAYLOAD)
    second = {**SECTIONAL_PAYLOAD, "race_id": "race-002", "race_name": "Second Race"}
    await ac.post("/api/tracksense/webhook", json=second)

    history = json.loads(store[f"tracksense:sectionals:{EPC}"])
    assert len(history) == 2
    assert history[0]["race_id"] == "race-001"
    assert history[1]["race_id"] == "race-002"


@pytest.mark.asyncio
async def test_webhook_rolling_window_drops_oldest_after_50(client_no_secret):
    ac, store = client_no_secret
    for i in range(52):
        payload = {**SECTIONAL_PAYLOAD, "race_id": f"race-{i:03d}"}
        await ac.post("/api/tracksense/webhook", json=payload)

    history = json.loads(store[f"tracksense:sectionals:{EPC}"])
    assert len(history) == 50
    assert history[0]["race_id"] == "race-002"   # first two dropped
    assert history[-1]["race_id"] == "race-051"


@pytest.mark.asyncio
async def test_webhook_bad_payload_returns_400(client_no_secret):
    ac, _ = client_no_secret
    r = await ac.post(
        "/api/tracksense/webhook",
        content=b'{"race_id": "x"}',  # missing required fields
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhook_empty_results_returns_zero_stored(client_no_secret):
    ac, _ = client_no_secret
    r = await ac.post("/api/tracksense/webhook", json={**SECTIONAL_PAYLOAD, "results": []})
    assert r.status_code == 200
    assert r.json()["horses_stored"] == 0


# ---------------------------------------------------------------------------
# Part 2 — Webhook: HMAC enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature_header(client_with_secret):
    ac, _ = client_with_secret
    r = await ac.post("/api/tracksense/webhook", json=SECTIONAL_PAYLOAD)
    assert r.status_code == 401
    assert r.json()["error"] == "invalid signature"


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_signature(client_with_secret):
    ac, _ = client_with_secret
    r = await ac.post(
        "/api/tracksense/webhook",
        json=SECTIONAL_PAYLOAD,
        headers={"X-TrackSense-Signature": "sha256=deadbeef"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_malformed_sig_prefix(client_with_secret):
    ac, _ = client_with_secret
    r = await ac.post(
        "/api/tracksense/webhook",
        json=SECTIONAL_PAYLOAD,
        headers={"X-TrackSense-Signature": "md5=abc123"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_valid_hmac_signature(client_with_secret):
    ac, _ = client_with_secret
    body = json.dumps(SECTIONAL_PAYLOAD).encode()
    r = await ac.post(
        "/api/tracksense/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-TrackSense-Signature": _sign(body, SECRET)},
    )
    assert r.status_code == 200
    assert r.json()["accepted"] is True


# ---------------------------------------------------------------------------
# Part 3 — get_hardware_and_historical_context
#
# `get_hardware_and_historical_context` does `from app.core.cache import cache_get` as a
# local import inside the function, so the correct patch target is
# `app.core.cache.cache_get` (the function is looked up fresh each call).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_returns_empty_for_unmapped_horse():
    from app.services.secretariat import get_hardware_and_historical_context
    with patch("app.core.cache.cache_get", new=AsyncMock(return_value=None)):
        result = await get_hardware_and_historical_context([{"horse_id": "unknown", "horse": "Ghost"}])
    assert result == {}


@pytest.mark.asyncio
async def test_context_returns_empty_when_no_sectionals():
    from app.services.secretariat import get_hardware_and_historical_context

    async def fake_get(key):
        if "map:" in key:
            return {"epc": EPC, "horse_name": HORSE_NAME}
        return None

    with patch("app.core.cache.cache_get", new=fake_get):
        result = await get_hardware_and_historical_context([{"horse_id": HORSE_ID, "horse": HORSE_NAME}])
    assert result == {}


@pytest.mark.asyncio
async def test_context_builds_context_string():
    from app.services.secretariat import get_hardware_and_historical_context

    sectionals_data = [
        {
            "race_name": "Gold Cup Trial",
            "completed_at": "2026-04-04T14:30:00Z",
            "sectionals": [
                {"gate_name": "2f",     "speed_kmh": 58.2},
                {"gate_name": "finish", "speed_kmh": 61.1},
            ],
        }
    ]

    async def fake_get(key):
        if "map:" in key:
            return {"epc": EPC, "horse_name": HORSE_NAME}
        if "sectionals:" in key:
            return sectionals_data
        return None

    with patch("app.core.cache.cache_get", new=fake_get):
        result = await get_hardware_and_historical_context([{"horse_id": HORSE_ID, "horse": HORSE_NAME}])

    assert HORSE_NAME in result
    ctx = result[HORSE_NAME]
    assert "TRACKSENSE HARDWARE DATA" in ctx
    assert "2f:" in ctx
    assert "finish:" in ctx
    assert "1 races" in ctx


@pytest.mark.asyncio
async def test_context_never_raises():
    from app.services.secretariat import get_hardware_and_historical_context

    async def exploding_get(key):
        raise RuntimeError("redis exploded")

    with patch("app.core.cache.cache_get", new=exploding_get):
        result = await get_hardware_and_historical_context([{"horse_id": HORSE_ID, "horse": HORSE_NAME}])
    assert result == {}


@pytest.mark.asyncio
async def test_context_trend_improving():
    from app.services.secretariat import get_hardware_and_historical_context

    # Speeds 48, 49, 50, 51, 52, 53 → career avg 50.5, last-3 avg 52.0 → improving
    sectionals_data = [
        {"race_name": f"Race {i}", "completed_at": "2026-01-01",
         "sectionals": [{"gate_name": "finish", "speed_kmh": 48.0 + i}]}
        for i in range(6)
    ]

    async def fake_get(key):
        if "map:" in key:
            return {"epc": EPC, "horse_name": HORSE_NAME}
        if "sectionals:" in key:
            return sectionals_data
        return None

    with patch("app.core.cache.cache_get", new=fake_get):
        result = await get_hardware_and_historical_context([{"horse_id": HORSE_ID, "horse": HORSE_NAME}])

    assert "improving" in result[HORSE_NAME]


@pytest.mark.asyncio
async def test_context_skips_horse_with_no_id():
    from app.services.secretariat import get_hardware_and_historical_context
    result = await get_hardware_and_historical_context([{"horse": "No ID Horse"}])
    assert result == {}


@pytest.mark.asyncio
async def test_context_uses_horse_name_key():
    from app.services.secretariat import get_hardware_and_historical_context

    sectionals_data = [
        {"race_name": "X", "completed_at": "2026-01-01",
         "sectionals": [{"gate_name": "finish", "speed_kmh": 60.0}]}
    ]

    async def fake_get(key):
        if "map:" in key:
            return {"epc": EPC, "horse_name": HORSE_NAME}
        if "sectionals:" in key:
            return sectionals_data
        return None

    with patch("app.core.cache.cache_get", new=fake_get):
        result = await get_hardware_and_historical_context([{"horse_id": HORSE_ID, "horse": HORSE_NAME}])

    assert HORSE_NAME in result
    assert len(result) == 1
