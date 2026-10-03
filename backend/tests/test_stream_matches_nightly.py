"""A user's on-demand analysis is built the way the graded nightly pick is.

The stream path used to build its own prompt on Haiku. Haiku lost the pick
experiment 15.7% to 24.5%, and the prompt had no chart figures, connections or
pedigree, so after a scratch a user could open a top pick the graded Secretariat
never made. These tests pin both halves: same builder, same model choice.
"""
import json
from contextlib import asynccontextmanager

import pytest

from app.services import secretariat as s

RACE = {"race_id": "IND_1790640000000-3", "race_number": 3, "runners": [], "region": "USA"}
ANALYSIS = json.dumps({"predicted_finish": {"first": {"horse_name": "A", "number": "#1"}}})


class _Stream:
    def __init__(self):
        async def gen():
            yield ANALYSIS
        self.text_stream = gen()

    async def get_final_message(self):
        class _U:
            input_tokens, output_tokens = 6000, 3000
            cache_read_input_tokens, cache_creation_input_tokens = 4000, 0

        class _M:
            usage = _U()
        return _M()


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    async def fake_build(race_data, **kw):
        seen["build_kwargs"] = kw
        return {"model": kw["model"], "max_tokens": 5000, "temperature": 0.2,
                "system": [], "messages": [{"role": "user", "content": "PROMPT"}]}

    @asynccontextmanager
    async def fake_stream(**kw):
        seen["stream_kwargs"] = kw
        yield _Stream()

    async def fake_log(**kw):
        seen["logged"] = kw

    monkeypatch.setattr(s, "build_analyze_request", fake_build)
    monkeypatch.setattr(s.client.messages, "stream", fake_stream)
    monkeypatch.setattr("app.core.llm_cost.log_call", fake_log)
    monkeypatch.setattr(s, "_store_prediction", lambda **kw: _noop())
    return seen


async def _noop():
    return None


async def _drain(gen):
    out = None
    async for kind, data in gen:
        if kind == "result":
            out = data
    return out


@pytest.mark.asyncio
async def test_the_stream_is_built_by_the_nightly_builder(captured):
    await _drain(s.stream_analyze_race(RACE, mode="medium", experience_level="advanced"))
    # The stream sends exactly what build_analyze_request returned.
    assert captured["stream_kwargs"]["messages"][0]["content"] == "PROMPT"
    assert captured["build_kwargs"]["mode"] == "medium"
    assert captured["build_kwargs"]["experience_level"] == "advanced"


@pytest.mark.asyncio
async def test_the_stream_uses_the_model_the_nightly_chose_for_this_race(captured):
    await _drain(s.stream_analyze_race(RACE))
    want = s.pick_model_for_race(RACE["race_id"])
    assert captured["build_kwargs"]["model"] == want
    assert captured["stream_kwargs"]["model"] == want


@pytest.mark.asyncio
async def test_with_no_experiment_running_that_is_sonnet(captured, monkeypatch):
    monkeypatch.setattr(s, "PICK_MODEL_AB_PERCENT", 0)
    await _drain(s.stream_analyze_race(RACE))
    assert captured["stream_kwargs"]["model"] == s.PICK_MODEL_DEFAULT == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_the_logged_model_and_cache_tokens_are_the_real_ones(captured):
    await _drain(s.stream_analyze_race(RACE))
    assert captured["logged"]["model"] == captured["stream_kwargs"]["model"]
    assert captured["logged"]["cache_read_tokens"] == 4000


@pytest.mark.asyncio
async def test_the_result_goes_through_the_shared_finisher(captured):
    result = await _drain(s.stream_analyze_race(RACE))
    assert result["predicted_finish"]["first"]["horse_name"] == "A"
