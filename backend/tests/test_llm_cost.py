"""Tests for LLM cost estimation — cache and batch pricing must stay honest."""
import pytest

from app.core.llm_cost import estimate_cost
from app.services.secretariat import SECRETARIAT_SYSTEM, _cached_system

HAIKU = "claude-haiku-4-5-20251001"  # $1/M input, $5/M output


def test_plain_call_cost():
    # 1M input + 1M output = $1 + $5
    assert estimate_cost(HAIKU, 1_000_000, 1_000_000) == pytest.approx(6.0)


def test_cache_read_bills_at_tenth():
    # 1M cache-read tokens = $0.10, not $1
    assert estimate_cost(HAIKU, 0, 0, cache_read_tokens=1_000_000) == pytest.approx(0.10)


def test_cache_write_bills_at_1_25x():
    assert estimate_cost(HAIKU, 0, 0, cache_write_tokens=1_000_000) == pytest.approx(1.25)


def test_batch_halves_token_cost():
    full = estimate_cost(HAIKU, 1_000_000, 1_000_000)
    batched = estimate_cost(HAIKU, 1_000_000, 1_000_000, batch=True)
    assert batched == pytest.approx(full / 2)


def test_batch_does_not_discount_web_search():
    # Web search is a flat per-call fee, not a token cost.
    cost = estimate_cost(HAIKU, 0, 0, web_searches=10, batch=True)
    assert cost == pytest.approx(0.10)


def test_cached_system_shape():
    blocks = _cached_system()
    assert len(blocks) == 1
    assert blocks[0]["text"] == SECRETARIAT_SYSTEM
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_cached_system_with_calibration_block():
    blocks = _cached_system("YOUR RECENT PERFORMANCE: ...")
    assert len(blocks) == 2
    assert blocks[1]["text"].startswith("YOUR RECENT PERFORMANCE")
    assert all(b["cache_control"] == {"type": "ephemeral"} for b in blocks)
