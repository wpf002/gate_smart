"""
Tests for the market-agreement calibration computed nightly and fed into the
MARKET DISCIPLINE prompt. All figures must be realized from stored results —
these tests lock the arithmetic so the prompt can never cite a fabricated edge.
"""
from types import SimpleNamespace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from nightly_recalibration import _market_calibration


def _p(is_fav, correct, odds):
    return SimpleNamespace(top_pick_is_favorite=is_fav, top_pick_correct=correct, top_pick_odds=odds)


def test_agree_fade_split_is_realized():
    # 40 agree (20 wins => 50%), 60 fade (12 wins => 20%)
    preds = [_p(True, i < 20, 2.0) for i in range(40)] + [_p(False, i < 12, 5.0) for i in range(60)]
    mc = _market_calibration(preds)
    assert mc is not None
    assert mc["agree_n"] == 40 and mc["fade_n"] == 60
    assert mc["agree_win_rate"] == 0.5
    assert mc["fade_win_rate"] == 0.2
    assert mc["fade_rate"] == 0.6


def test_returns_none_on_thin_sample():
    assert _market_calibration([_p(True, True, 2.0) for _ in range(10)]) is None
    # enough total but too few fades
    preds = [_p(True, True, 2.0) for _ in range(80)] + [_p(False, False, 5.0) for _ in range(5)]
    assert _market_calibration(preds) is None


def test_ignores_rows_without_market_context():
    preds = ([_p(None, True, None) for _ in range(50)] +
             [_p(True, i < 10, 2.0) for i in range(30)] +
             [_p(False, i < 3, 6.0) for i in range(30)])
    mc = _market_calibration(preds)
    assert mc["sample"] == 60  # the 50 None-favorite rows are excluded


def test_longshot_underperforms_flag():
    # Longshot picks at 5/1 (implied 1/6 ≈ 16.7%) that win only 5% -> underperform
    preds = ([_p(True, i < 10, 2.0) for i in range(30)] +
             [_p(False, i < 2, 5.0) for i in range(40)])  # 40 longshots, 5% win < 16.7% implied
    mc = _market_calibration(preds)
    assert mc["longshot_underperforms"] is True


def test_longshot_beating_price_not_flagged():
    # Longshot picks at 5/1 that win 30% (> implied 16.7%) -> NOT flagged
    preds = ([_p(True, i < 10, 2.0) for i in range(30)] +
             [_p(False, i < 12, 5.0) for i in range(40)])  # 30% win > implied
    mc = _market_calibration(preds)
    assert mc["longshot_underperforms"] is False
