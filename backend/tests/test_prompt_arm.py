"""
The honest-prompt test has to compare one thing: the system prompt.

The legacy prompt tells Secretariat to lead with speed figures, running styles,
workouts and trainer percentages it never receives for races since 2024. The
honest arm describes the data it does receive. These tests hold the properties
that make the comparison valid: the split is deterministic and independent of
the other experiments, every path that analyzes a race uses the same arm, the
stored row records that arm, and the legacy arm stays exactly today's prompt.
"""
import hashlib
from pathlib import Path

import pytest

import app.services.secretariat as sec
from app.services.fade_reason import DATA_FADE_REASONS, FADE_REASONS

BACKEND = Path(__file__).resolve().parent.parent
NIGHTLY = (BACKEND / "scripts" / "nightly_predict_all.py").read_text()

RACE = {
    "race_id": "GP_1786752000000-1",
    "runners": [
        {"horse_name": "Alpha", "number": "1", "odds": "5/2"},
        {"horse_name": "Bravo", "number": "2", "odds": "9/5"},
    ],
}


def _race_ids(n=4000):
    return [f"TRK_{1700000000000 + i * 86400000}-{i % 12 + 1}" for i in range(n)]


def _race_in(arm):
    return next(r for r in _race_ids() if sec.prompt_arm_for_race(r) == arm)


@pytest.fixture
def patched(monkeypatch):
    seen = {}

    async def no_hardware(runners):
        return {}

    async def fake_cal(race_id=None, arm=None):
        seen["cal_arm"] = arm
        return f"YOUR RECENT PERFORMANCE ({arm})"

    async def no_lessons(race_id=None):
        return ""

    monkeypatch.setattr(sec, "get_hardware_and_historical_context", no_hardware)
    monkeypatch.setattr(sec, "get_calibration_context", fake_cal)
    monkeypatch.setattr(sec, "get_lessons_context", no_lessons)
    monkeypatch.setattr(sec, "PROMPT_HONEST_PERCENT", 50)
    return seen


def test_the_split_is_deterministic_and_close_to_half(monkeypatch):
    monkeypatch.setattr(sec, "PROMPT_HONEST_PERCENT", 50)
    ids = _race_ids()
    arms = [sec.prompt_arm_for_race(r) for r in ids]
    assert arms == [sec.prompt_arm_for_race(r) for r in ids]
    share = arms.count(sec.PROMPT_ARM_HONEST) / len(arms)
    assert 0.46 < share < 0.54


def test_the_split_is_independent_of_the_lesson_experiment(monkeypatch):
    """Each lesson arm should hold both prompts in about equal measure, or the
    prompt test would be measuring lessons too."""
    monkeypatch.setattr(sec, "PROMPT_HONEST_PERCENT", 50)
    by_lesson_arm = {True: [], False: []}
    for r in _race_ids():
        lesson_bucket = int(hashlib.md5(f"lessons:{r}".encode()).hexdigest()[:8], 16) % 100 < 50
        by_lesson_arm[lesson_bucket].append(sec.prompt_arm_for_race(r) == sec.PROMPT_ARM_HONEST)
    for flags in by_lesson_arm.values():
        assert 0.44 < sum(flags) / len(flags) < 0.56


def test_zero_ends_the_test_and_one_hundred_ships_it(monkeypatch):
    monkeypatch.setattr(sec, "PROMPT_HONEST_PERCENT", 0)
    assert {sec.prompt_arm_for_race(r) for r in _race_ids(300)} == {sec.PROMPT_ARM_LEGACY}
    monkeypatch.setattr(sec, "PROMPT_HONEST_PERCENT", 100)
    assert {sec.prompt_arm_for_race(r) for r in _race_ids(300)} == {sec.PROMPT_ARM_HONEST}


async def test_the_legacy_arm_sends_todays_prompt(patched):
    race = {**RACE, "race_id": _race_in(sec.PROMPT_ARM_LEGACY)}
    kwargs = await sec.build_analyze_request(race, mode="medium", experience_level="advanced")
    assert kwargs["system"][0]["text"] == sec.SECRETARIAT_SYSTEM
    assert patched["cal_arm"] == sec.PROMPT_ARM_LEGACY
    prompt = kwargs["messages"][0]["content"]
    assert "how that shape affects the pace projection" in prompt
    assert "Beyer trajectory" in prompt  # the legacy advanced block, untouched


async def test_the_honest_arm_swaps_prompt_calibration_and_wording(patched):
    race = {**RACE, "race_id": _race_in(sec.PROMPT_ARM_HONEST)}
    kwargs = await sec.build_analyze_request(race, mode="medium", experience_level="advanced")
    assert kwargs["system"][0]["text"] == sec.SECRETARIAT_SYSTEM_HONEST
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert patched["cal_arm"] == sec.PROMPT_ARM_HONEST
    prompt = kwargs["messages"][0]["content"]
    assert "don't assign running styles the data doesn't show" in prompt
    assert "Beyer" not in prompt and "speed figures" not in prompt


async def test_a_live_reanalysis_uses_the_same_arm_as_the_nightly_pick(patched, monkeypatch):
    """A scratch or rider change regenerates the analysis on the live stream
    path. It must not flip the race to the other prompt."""
    import types

    captured = {}

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def text_stream(self):
            async def gen():
                yield '{"predicted_finish": {}}'
            return gen()

        async def get_final_message(self):
            return None

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return FakeStream()

    monkeypatch.setattr(sec, "client", types.SimpleNamespace(messages=types.SimpleNamespace(stream=fake_stream)))
    for arm, text in ((sec.PROMPT_ARM_HONEST, sec.SECRETARIAT_SYSTEM_HONEST),
                      (sec.PROMPT_ARM_LEGACY, sec.SECRETARIAT_SYSTEM)):
        race = {**RACE, "race_id": _race_in(arm)}
        async for _ in sec.stream_analyze_race(race, mode="medium"):
            pass
        assert captured["system"][0]["text"] == text
        assert patched["cal_arm"] == arm


def test_the_honest_prompt_asks_for_nothing_it_does_not_receive():
    text = sec.SECRETARIAT_SYSTEM_HONEST
    assert "THE DATA YOU DO NOT RECEIVE" in text
    for instruction in ("Beyer Speed Figure trajectory", "PACE PRESSURE INDEX", "bullet",
                        "gate work", "layoff win %", "Count runners by running style"):
        assert instruction not in text, instruction
    # The legacy prompt is kept verbatim as the control.
    assert "Beyer Speed Figure trajectory" in sec.SECRETARIAT_SYSTEM


async def test_calibration_names_only_data_backed_fade_reasons_in_the_honest_arm(monkeypatch):
    class Cal:
        sample_size = 500
        rolling_win_rate = 0.26
        weak_spots, strong_spots, lessons = [], [], []
        market_calibration = {"agree_n": 150, "fade_n": 350, "sample": 500, "agree_win_rate": 0.39,
                              "fade_win_rate": 0.2, "fade_rate": 0.7}

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *_):
            return Cal()

    import app.core.database as dbmod
    monkeypatch.setattr(dbmod, "_AsyncSessionLocal", Session)
    honest = await sec.get_calibration_context("R-1", arm=sec.PROMPT_ARM_HONEST)
    legacy = await sec.get_calibration_context("R-1", arm=sec.PROMPT_ARM_LEGACY)
    for key in DATA_FADE_REASONS:
        assert f"    {key} — " in honest
    for key in set(FADE_REASONS) - set(DATA_FADE_REASONS):
        assert f"    {key} — " not in honest
        assert f"    {key} — " in legacy
    assert "bounce off a peak" in legacy and "bounce" not in honest


def test_the_stored_row_records_the_arm_from_the_same_helper():
    assert '"prompt_arm": prompt_arm_for_race(race_id) if lock_source == "nightly" else None' in NIGHTLY


def test_prewarm_keys_on_the_cached_prefix_not_the_per_race_lessons():
    """The lesson block rides uncached after the last cache marker. Hashing it
    made nearly every race its own prefix: 45 pre-warm calls on 2026-09-15."""
    from scripts.nightly_predict_all import cached_prefix

    base = [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "CAL", "cache_control": {"type": "ephemeral"}}]
    race_a = base + [{"type": "text", "text": "LESSONS: a, b"}]
    race_b = base + [{"type": "text", "text": "LESSONS: c"}]
    assert cached_prefix(race_a) == cached_prefix(race_b) == base
    assert cached_prefix([{"type": "text", "text": "no marker"}]) == []
    assert "system=_prefix" in NIGHTLY
