"""Tests for the shared analyze-request builder (sync + batch paths)."""
import pytest

import app.services.secretariat as sec


@pytest.fixture
def patched(monkeypatch):
    async def no_hardware(runners):
        return {}

    async def fake_cal():
        return "YOUR RECENT PERFORMANCE: 19% over 2404 races."

    monkeypatch.setattr(sec, "get_hardware_and_historical_context", no_hardware)
    monkeypatch.setattr(sec, "get_calibration_context", fake_cal)


RACE = {
    "race_id": "ALB_123-5",
    "runners": [
        {"horse_name": "Alpha", "number": "1", "odds": "5/2"},
        {"horse_name": "Bravo", "number": "2", "odds": "9/5"},
    ],
}


@pytest.mark.asyncio
async def test_builder_returns_cached_system_blocks(patched):
    kwargs = await sec.build_analyze_request(RACE, mode="medium")
    system = kwargs["system"]
    assert isinstance(system, list) and len(system) == 2
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[1]["text"].startswith("YOUR RECENT PERFORMANCE")
    assert system[1]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_builder_prompt_contains_race_data_not_calibration(patched):
    kwargs = await sec.build_analyze_request(RACE, mode="medium")
    prompt = kwargs["messages"][0]["content"]
    assert "Alpha" in prompt and "Bravo" in prompt
    # calibration moved to the cached system block — must not be re-billed in the prompt
    assert "YOUR RECENT PERFORMANCE" not in prompt
    assert kwargs["model"].startswith("claude-haiku")
    assert kwargs["max_tokens"] == 5000


@pytest.mark.asyncio
async def test_finish_analysis_parses_and_dedupes():
    raw = (
        '{"predicted_finish": {"first": {"horse_name": "Alpha", "number": "#1"},'
        '"second": {"horse_name": "Alpha", "number": "#1"},'
        '"third": {"horse_name": "Bravo", "number": "#2"}}}'
    )
    result = sec.finish_analysis(raw)
    pf = result["predicted_finish"]
    assert pf["first"]["horse_name"] == "Alpha"
    assert pf["second"]["horse_name"] == "Bravo"  # duplicate collapsed
    assert pf["third"] is None
