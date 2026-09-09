"""The daily hard cap must stop unattended spend without touching users.

The cap exists because the nightly slate analyzes the whole NA racecard whether
or not anyone opens a race, so a failing run can re-bill a full slate with
nobody watching. It must therefore hold three properties, each pinned below:

  1. It never blocks an interactive call. Someone waiting on a race gets their
     analysis regardless of spend — that is the module's founding principle and
     the cap does not weaken it.
  2. It fails OPEN. An unreadable ledger reads as $0 spent, so a database
     problem can never halt the slate on its own.
  3. It is off unless configured, so a deployment that never sets
     LLM_DAILY_CAP_USD behaves exactly as it did before.
"""
import importlib
import os
from unittest.mock import AsyncMock, patch

import pytest


def _load(cap: str):
    """Reload llm_cost with a given cap — the threshold is read at import."""
    os.environ["LLM_DAILY_CAP_USD"] = cap
    import app.core.llm_cost as m

    return importlib.reload(m)


class _FakeClient:
    """Minimal stand-in for the Anthropic async client."""

    def __init__(self):
        self.messages = type("M", (), {})()
        self.messages.create = AsyncMock(
            return_value=type("R", (), {"usage": None, "content": []})()
        )


@pytest.fixture
def cap_25():
    m = _load("25")
    yield m
    _load("0")


async def test_disabled_by_default_never_blocks():
    m = _load("0")
    with patch.object(m, "today_spend_usd", AsyncMock(return_value=999.0)):
        await m.enforce_daily_cap("nightly")  # must not raise


async def test_under_cap_allows(cap_25):
    with patch.object(cap_25, "today_spend_usd", AsyncMock(return_value=10.0)):
        await cap_25.enforce_daily_cap("nightly")


async def test_at_cap_blocks_unattended(cap_25):
    with patch.object(cap_25, "today_spend_usd", AsyncMock(return_value=25.0)):
        with pytest.raises(cap_25.DailyBudgetExceeded):
            await cap_25.enforce_daily_cap("nightly")


async def test_interactive_call_served_over_cap(cap_25):
    """The whole point: a person waiting on a race is never refused."""
    client = _FakeClient()
    with patch.object(cap_25, "today_spend_usd", AsyncMock(return_value=999.0)), \
            patch.object(cap_25, "log_call", AsyncMock()):
        await cap_25.tracked_create(client, endpoint="analyze_race")
    client.messages.create.assert_awaited_once()


async def test_unattended_call_blocked_over_cap(cap_25):
    client = _FakeClient()
    with patch.object(cap_25, "today_spend_usd", AsyncMock(return_value=999.0)), \
            patch.object(cap_25, "log_call", AsyncMock()):
        with pytest.raises(cap_25.DailyBudgetExceeded):
            await cap_25.tracked_create(
                client, endpoint="nightly_predict_all", interactive=False
            )
    # Blocked before the API was ever called — that is where the money is saved.
    client.messages.create.assert_not_awaited()


async def test_fails_open_when_ledger_unreadable(cap_25):
    """today_spend_usd swallows DB errors and returns 0.0; the cap inherits that,
    so a database outage cannot silently stop the nightly run."""
    def _boom(*a, **k):
        raise RuntimeError("database is down")

    with patch("app.core.database._AsyncSessionLocal", _boom):
        cap_25._budget_cache = None
        assert await cap_25.today_spend_usd(use_cache=False) == 0.0
        await cap_25.enforce_daily_cap("nightly")  # must not raise
