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
