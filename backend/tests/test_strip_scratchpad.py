"""Tests for advisor scratchpad stripping (no visible deliberation)."""
from app.services.secretariat import _strip_scratchpad


def test_strips_closed_scratchpad():
    raw = (
        "<scratchpad>Gallant Fox — wait, no. Let me reconsider. The cases are...\n"
        "Actually it's never.</scratchpad>\n\n"
        "**The answer is zero.** No horse has done this."
    )
    out = _strip_scratchpad(raw)
    assert out == "**The answer is zero.** No horse has done this."
    assert "scratchpad" not in out.lower()
    assert "wait" not in out.lower()


def test_keeps_after_last_close_when_multiple():
    raw = "<scratchpad>a</scratchpad>mid<scratchpad>b</scratchpad>FINAL"
    assert _strip_scratchpad(raw) == "FINAL"


def test_closed_but_answer_inside_is_salvaged_not_empty():
    # Model put the whole answer inside the scratchpad and wrote nothing after —
    # must NOT return empty.
    raw = "<scratchpad>The answer is Citation (1948).</scratchpad>"
    out = _strip_scratchpad(raw)
    assert out != ""
    assert "scratchpad" not in out.lower()
    assert "Citation" in out


def test_unclosed_scratchpad_is_never_empty():
    raw = "<scratchpad>let me think, the answer is zero"
    out = _strip_scratchpad(raw)
    assert out != ""
    assert "scratchpad" not in out.lower()


def test_no_scratchpad_passes_through():
    raw = "**Citation (1948)** is the answer — a clean, direct response."
    assert _strip_scratchpad(raw) == raw


def test_case_insensitive_tags():
    raw = "<ScratchPad>noise</SCRATCHPAD>Answer."
    assert _strip_scratchpad(raw) == "Answer."


def test_empty_and_none_safe():
    assert _strip_scratchpad("") == ""
    assert _strip_scratchpad(None) is None
