"""Shared pytest fixtures.

The API rate limiter uses in-memory storage that persists across tests within
a run, so a test file that hits a limited endpoint enough times would trip the
limit and make an unrelated later test fail with a spurious 429. Rate limiting
isn't the unit under test anywhere, so disable it globally for the suite.
"""
import pytest


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    from app.core.limiter import limiter
    previous = limiter.enabled
    limiter.enabled = False
    try:
        yield
    finally:
        limiter.enabled = previous
