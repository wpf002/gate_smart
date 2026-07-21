"""
The daily digest scorecard must count ONLY Secretariat's nightly morning-line
slate. Live re-analyses (mode != auto_daily), per-user predictions, and phantom
rows with no finisher must never pad or skew the win rate — this is the exact
drift found on 2026-07-11/12/13 (a phantom no-result loss and two live-mode
picks leaking into the daily reports).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from nightly_accuracy import _report_scoring_set


def _row(mode="auto_daily", user_id=None, actual_first="Winner", top_correct=True):
    return {"analysis_mode": mode, "user_id": user_id,
            "actual_first": actual_first, "top_correct": top_correct}


def test_keeps_only_nightly_slate():
    settled = [
        _row(),                                   # nightly pick — counts
        _row(mode="medium"),                      # live re-analysis — excluded
        _row(user_id=42),                         # per-user prediction — excluded
        _row(actual_first=None),                  # phantom, no finisher — excluded
        _row(actual_first=""),                    # phantom, empty finisher — excluded
        _row(),                                   # nightly pick — counts
    ]
    kept = _report_scoring_set(settled)
    assert len(kept) == 2
    assert all(r["analysis_mode"] == "auto_daily" and r["user_id"] is None and r["actual_first"]
               for r in kept)


def test_live_mode_win_does_not_inflate():
    # A winning live-mode pick must NOT count — mirrors the 7/13 case where a
    # mode=medium winner had inflated the report.
    settled = [_row(mode="medium", top_correct=True)] + [_row(top_correct=False) for _ in range(4)]
    kept = _report_scoring_set(settled)
    wins = sum(1 for s in kept if s["top_correct"])
    assert len(kept) == 4 and wins == 0  # 4 nightly losses, the live win excluded


def test_empty_when_no_nightly_rows():
    assert _report_scoring_set([_row(mode="medium"), _row(user_id=1)]) == []
