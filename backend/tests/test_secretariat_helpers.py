"""
Unit tests for secretariat._parse_json — the JSON extraction helper
introduced to fix truncated/malformed Claude responses.
"""
import pytest
import json
from app.services.secretariat import _parse_json


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------

def test_parse_clean_json_object():
    assert _parse_json('{"answer": "hello"}') == {"answer": "hello"}


def test_parse_json_with_whitespace():
    assert _parse_json('  \n{"key": 1}\n  ') == {"key": 1}


def test_parse_markdown_fenced_json():
    text = '```json\n{"answer": "hello"}\n```'
    assert _parse_json(text) == {"answer": "hello"}


def test_parse_markdown_fenced_no_language_tag():
    text = '```\n{"answer": "hello"}\n```'
    assert _parse_json(text) == {"answer": "hello"}


def test_parse_json_with_leading_prose():
    """Claude sometimes adds a sentence before the JSON object."""
    text = 'Here is the analysis:\n{"result": "ok", "value": 42}'
    result = _parse_json(text)
    assert result == {"result": "ok", "value": 42}


def test_parse_json_with_trailing_text():
    text = '{"answer": "test"}\n\nLet me know if you need more.'
    assert _parse_json(text) == {"answer": "test"}


def test_parse_nested_json():
    data = {"runners": [{"name": "Arkle", "score": 90}], "confidence": "high"}
    assert _parse_json(json.dumps(data)) == data


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_parse_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_json('{"unterminated": "string')


def test_parse_raises_on_empty_string():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_json("")


def test_parse_raises_on_no_json_object():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_json("just plain text with no braces")


# ---------------------------------------------------------------------------
# answer_betting_question — extracts answer string from Claude's JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_betting_question_extracts_answer_from_json():
    """
    Claude's system prompt forces JSON output even for free-form answers.
    answer_betting_question must extract the 'answer' string, not return raw JSON.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    fake_content = MagicMock()
    fake_content.text = '{"answer": "A furlong is 1/8 of a mile."}'
    fake_response = MagicMock()
    fake_response.content = [fake_content]

    with patch("app.services.secretariat.client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=fake_response)
        from app.services.secretariat import answer_betting_question
        result = await answer_betting_question("What is a furlong?")

    assert result == "A furlong is 1/8 of a mile."
    assert not result.startswith("{")


@pytest.mark.asyncio
async def test_answer_betting_question_handles_markdown_fenced_json():
    from unittest.mock import AsyncMock, MagicMock, patch

    fake_content = MagicMock()
    fake_content.text = '```json\n{"answer": "SP means Starting Price."}\n```'
    fake_response = MagicMock()
    fake_response.content = [fake_content]

    with patch("app.services.secretariat.client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=fake_response)
        from app.services.secretariat import answer_betting_question
        result = await answer_betting_question("What is SP?")

    assert result == "SP means Starting Price."
