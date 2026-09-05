"""
Per-call Claude API cost tracking.

Wraps `client.messages.create` with usage extraction and DB logging so every
LLM call writes a row to `llm_call_log`. Daily burn is then a single SQL query.
"""
import datetime
import logging
import os
import time
from typing import Any

log = logging.getLogger(__name__)


# --- Daily spend observability ---------------------------------------------
# Alert-only. Nothing here ever blocks a call: functionality always wins, and
# cost is controlled by routing + caching + idempotent retries instead.
# Set LLM_SOFT_ALERT_USD=0 to silence.
LLM_SOFT_ALERT_USD = float(os.getenv("LLM_SOFT_ALERT_USD", "25"))
_BUDGET_CACHE_TTL_SECONDS = 60

# (spend_usd, fetched_at_monotonic, date) — avoids a DB round-trip per call.
_budget_cache: tuple[float, float, datetime.date] | None = None


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


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    web_searches: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    batch: bool = False,
) -> float:
    """Estimate USD cost. Cache reads bill at 0.1x input, writes at 1.25x.
    Batch API calls get a flat 50% discount on all token costs."""
    p = _price_lookup(model)
    token_cost = (
        (input_tokens / 1_000_000) * p["input"]
        + (cache_read_tokens / 1_000_000) * p["input"] * 0.1
        + (cache_write_tokens / 1_000_000) * p["input"] * 1.25
        + (output_tokens / 1_000_000) * p["output"]
    )
    if batch:
        token_cost *= 0.5
    return token_cost + web_searches * WEB_SEARCH_USD_PER_CALL


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
    user_id: int | None = None,
    batch: bool = False,
) -> None:
    """Write a single row to llm_call_log. Never raises — cost logging must not break the app.

    user_id=None for background/system calls; set to the authenticated user's id
    for on-demand calls so admin dashboards can attribute usage per user.
    batch=True applies the Batches API 50% discount to the cost estimate.
    """
    try:
        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import LLMCallLog

        cost = estimate_cost(
            model,
            input_tokens,
            output_tokens,
            web_searches,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            batch=batch,
        )
        row = LLMCallLog(
            call_date=datetime.date.today(),
            endpoint=endpoint,
            model=model,
            user_id=user_id,
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


async def today_spend_usd(*, use_cache: bool = True) -> float:
    """Sum est_cost_usd from llm_call_log for today. Fails OPEN (returns 0.0).

    Cost accounting must never take the app down, so any DB problem here is
    logged and treated as "no spend recorded" — the call proceeds.
    """
    global _budget_cache
    today = datetime.date.today()
    if use_cache and _budget_cache is not None:
        spend, fetched_at, cached_day = _budget_cache
        if cached_day == today and (time.monotonic() - fetched_at) < _BUDGET_CACHE_TTL_SECONDS:
            return spend
    try:
        from sqlalchemy import func, select

        from app.core.database import _AsyncSessionLocal
        from app.models.accuracy import LLMCallLog

        async with _AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.coalesce(func.sum(LLMCallLog.est_cost_usd), 0.0)).where(
                    LLMCallLog.call_date == today
                )
            )
            spend = float(result.scalar() or 0.0)
        _budget_cache = (spend, time.monotonic(), today)
        return spend
    except Exception as e:
        log.warning("llm_cost.today_spend_usd failed (failing open): %s", e)
        return 0.0


async def warn_if_over_soft_budget(endpoint: str) -> None:
    """Log loudly if today's spend passes the soft alert threshold.

    Deliberately NEVER blocks a call — this is an alarm, not a valve. Spend
    control comes from routing and caching, not from refusing work.
    """
    if LLM_SOFT_ALERT_USD <= 0:
        return
    spend = await today_spend_usd()
    if spend >= LLM_SOFT_ALERT_USD:
        log.error(
            "llm_cost: SOFT BUDGET ALERT — $%.2f today (threshold $%.2f), still serving %s. "
            "Investigate if unexpected; nothing has been blocked.",
            spend, LLM_SOFT_ALERT_USD, endpoint,
        )


async def tracked_create(client, *, endpoint: str, user_id: int | None = None, **create_kwargs) -> Any:
    """Drop-in wrapper for `client.messages.create(...)` that logs cost.

    Pass `endpoint="analyze_race"` (or similar) so daily breakdowns can group by feature.
    Pass `user_id` so per-user usage can be attributed (omit for background jobs).
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
        user_id=user_id,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_read or 0,
        cache_write_tokens=cache_write or 0,
        web_searches=_count_web_searches(response),
    )
    global _budget_cache
    _budget_cache = None  # force a fresh read on the next cap check
    return response
