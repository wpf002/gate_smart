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


def _pp(is_fav, correct, odds, payoff):
    """Row with an official win payoff attached."""
    r = _p(is_fav, correct, odds)
    r.top_pick_win_payoff = payoff
    return r


def test_longshot_roi_computed_from_real_payoffs():
    # 50 longshots at 5/1: 5 winners paying $12 each -> returned 60 on 100 staked
    rows = ([_pp(False, True, 5.0, 12.0) for _ in range(5)]
            + [_pp(False, False, 5.0, 0.0) for _ in range(45)]
            + [_pp(True, True, 2.0, 6.0) for _ in range(30)]
            + [_pp(True, False, 2.0, 0.0) for _ in range(30)])
    mc = _market_calibration(rows)
    assert mc["longshot_roi_n"] == 50
    assert mc["longshot_roi"] == -0.4          # (60-100)/100
    assert mc["longshot_win_rate"] == 0.1
    # short-price group: 60 bets, 30 winners x $6 = 180 on 120 staked -> +50%
    assert mc["short_price_roi_n"] == 60
    assert mc["short_price_roi"] == 0.5


def test_roi_omitted_when_sample_too_thin():
    """Only 10 longshots — too thin to cite, so no longshot ROI is claimed."""
    rows = ([_pp(True, False, 2.0, 0.0) for _ in range(40)]     # agree, short price
            + [_pp(False, False, 2.0, 0.0) for _ in range(30)]  # fade, short price
            + [_pp(False, True, 5.0, 12.0) for _ in range(10)])  # fade, longshot
    mc = _market_calibration(rows)
    assert mc is not None
    assert "longshot_roi" not in mc
    assert mc["short_price_roi_n"] == 70  # the short-price group is big enough


def test_unpriced_rows_excluded_from_roi():
    rows = ([_pp(False, True, 5.0, 12.0) for _ in range(5)]
            + [_pp(False, False, 5.0, 0.0) for _ in range(45)]
            + [_pp(False, False, 5.0, None) for _ in range(20)]   # unpriced
            + [_pp(True, False, 2.0, 0.0) for _ in range(30)])
    mc = _market_calibration(rows)
    assert mc["longshot_roi_n"] == 50  # the 20 unpriced longshots don't count
