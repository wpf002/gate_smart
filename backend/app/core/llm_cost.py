"""
Per-call Claude API cost tracking.

Wraps `client.messages.create` with usage extraction and DB logging so every
LLM call writes a row to `llm_call_log`. Daily burn is then a single SQL query.
"""
import datetime
import logging
from typing import Any

log = logging.getLogger(__name__)


# Anthropic public pricing (USD per 1M tokens). Update if Anthropic raises prices.
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-haiku-4-5":           {"input": 1.0, "output": 5.0},
    "claude-sonnet-4-6":          {"input": 3.0, "output": 15.0},
    "claude-opus-4-7":            {"input": 15.0, "output": 75.0},
}

# Anthropic web-search tool: $10 per 1,000 searches.
WEB_SEARCH_USD_PER_CALL = 0.01


def _price_lookup(model: str) -> dict:
    if model in PRICING:
        return PRICING[model]
    for key, p in PRICING.items():
        if model.startswith(key):
            return p
    log.warning("llm_cost: unknown model %s, using sonnet pricing as estimate", model)
    return PRICING["claude-sonnet-4-6"]


def estimate_cost(model: str, input_tokens: int, output_tokens: int, web_searches: int = 0) -> float:
    p = _price_lookup(model)
    return (
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"]
        + web_searches * WEB_SEARCH_USD_PER_CALL
    )


def _count_web_searches(response) -> int:
    """Count server_tool_use blocks for web_search in a response."""
    try:
        blocks = getattr(response, "content", []) or []
        return sum(
            1 for b in blocks
            if getattr(b, "type", "") == "server_tool_use"
            and getattr(b, "name", "") == "web_search"
        )
    except Exception:
        return 0


async def log_call(
    *,
    endpoint: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    web_searches: int = 0,
) -> None:
    """Write a single row to llm_call_log. Never raises — cost logging must not break the app."""
    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import LLMCallLog

        cost = estimate_cost(model, input_tokens + cache_read_tokens + cache_write_tokens, output_tokens, web_searches)
        row = LLMCallLog(
            call_date=datetime.date.today(),
            endpoint=endpoint,
            model=model,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            cache_read_tokens=int(cache_read_tokens),
            cache_write_tokens=int(cache_write_tokens),
            web_searches=int(web_searches),
            est_cost_usd=float(cost),
        )
        async with _AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
    except Exception as e:
        log.warning("llm_cost.log_call failed: %s", e)


async def tracked_create(client, *, endpoint: str, **create_kwargs) -> Any:
    """Drop-in wrapper for `client.messages.create(...)` that logs cost.

    Pass `endpoint="analyze_race"` (or similar) so daily breakdowns can group by feature.
    All other kwargs are forwarded verbatim.
    """
    response = await client.messages.create(**create_kwargs)
    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "input_tokens", 0) if usage else 0
    out_tok = getattr(usage, "output_tokens", 0) if usage else 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) if usage else 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) if usage else 0

    await log_call(
        endpoint=endpoint,
        model=create_kwargs.get("model", "unknown"),
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_read or 0,
        cache_write_tokens=cache_write or 0,
        web_searches=_count_web_searches(response),
    )
    return response
