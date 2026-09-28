"""Tests for smoke-check alert classification (pure logic)."""
from app.services.smoke_check import _classify_api_error


def test_credit_exhausted_alerts_595():
    msg = (
        "Error code: 400 - {'type': 'error', 'error': {'type': "
        "'invalid_request_error', 'message': 'Your credit balance is too low to "
        "access the Anthropic API. Please go to Plans & Billing to upgrade or "
        "purchase credits.'}}"
    )
    out = _classify_api_error(msg, 400)
    assert out is not None
    assert out[1] == 595
    assert "credit balance" in out[0].lower()


def test_auth_failure_alerts_595():
    out = _classify_api_error("authentication_error: invalid x-api-key", 401)
    assert out is not None
    assert out[1] == 595


def test_403_alerts_595():
    out = _classify_api_error("permission denied", 403)
    assert out is not None
    assert out[1] == 595


def test_transient_error_does_not_alert():
    assert _classify_api_error("Connection timed out", None) is None
    assert _classify_api_error("503 service unavailable", 503) is None
    assert _classify_api_error("overloaded_error", 529) is None


def test_empty_message_does_not_alert():
    assert _classify_api_error("", None) is None
    assert _classify_api_error(None, None) is None


# ── Freshness probes ────────────────────────────────────────────────────────
#
# 2026-09-27: the Anthropic account ran out of credits, the nightly produced no
# picks, and the missing-report alert then re-fired every 30 minutes for a day
# that can never be settled. An alert that cannot be cleared is one the owner
# learns to ignore.
import datetime
from types import SimpleNamespace

import pytest

from app.services import smoke_check


class _Session:
    """Answers the probe's queries in order: the pick count, then the report."""

    def __init__(self, picked, report=None):
        self.picked = picked
        self.report = report

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def scalar(self, *_a, **_k):
        return self.picked

    async def execute(self, *_a, **_k):
        return SimpleNamespace(scalar_one_or_none=lambda: self.report)


def _patch_db(monkeypatch, session):
    import app.core.database as dbm
    monkeypatch.setattr(dbm, "_AsyncSessionLocal", lambda: session)
    # After the stale-after hour, so the probe actually runs.
    monkeypatch.setattr(smoke_check, "_ACCURACY_STALE_AFTER_HOUR_UTC", 0)


@pytest.mark.asyncio
async def test_a_day_with_no_picks_expects_no_report(monkeypatch):
    _patch_db(monkeypatch, _Session(picked=0))
    assert await smoke_check._check_accuracy_freshness() is None


@pytest.mark.asyncio
async def test_a_settled_day_missing_its_report_still_alerts(monkeypatch):
    _patch_db(monkeypatch, _Session(picked=140, report=None))
    label, code = await smoke_check._check_accuracy_freshness()
    assert code == 599 and "No accuracy report" in label


@pytest.mark.asyncio
async def test_a_report_that_never_emailed_still_alerts(monkeypatch):
    row = SimpleNamespace(email_sent=False)
    _patch_db(monkeypatch, _Session(picked=140, report=row))
    label, code = await smoke_check._check_accuracy_freshness()
    assert code == 598


@pytest.mark.asyncio
async def test_a_healthy_day_is_silent(monkeypatch):
    row = SimpleNamespace(email_sent=True)
    _patch_db(monkeypatch, _Session(picked=140, report=row))
    assert await smoke_check._check_accuracy_freshness() is None


def test_the_nightly_stops_instead_of_retrying_a_dry_account():
    """137 races x 2 refused calls is not a retry strategy."""
    from pathlib import Path

    nightly = (Path(__file__).resolve().parent.parent / "scripts" / "nightly_predict_all.py").read_text()
    assert "raise CreditsExhausted(str(e)) from e" in nightly
    assert "except CreditsExhausted as e:" in nightly
    assert "if is_billing_error(e):" in nightly

    from app.core.llm_cost import CreditsExhausted, is_billing_error
    import anthropic

    err = anthropic.APIStatusError(
        "Error code: 400 - your credit balance is too low",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body=None,
    )
    assert is_billing_error(err)
    assert not is_billing_error(RuntimeError("upstream 503"))
    assert issubclass(CreditsExhausted, RuntimeError)
