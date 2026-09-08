"""
Deterministic re-ranking of Secretariat's own top four.

The measured weakness has never been finding contenders — the winner is in the
top four about 69% of the time — it is ORDERING them. One ordering error
dominates all others: when Secretariat puts a long-priced horse first, it is
usually wrong, and the horse it ranked second usually beats it.

Measured over 14,930 settled races, restricted to races where the top pick is
NOT the favorite and is priced at least 2x the favorite's morning line:

    races   pick #1 wins   pick #2 wins   gain
    4,318         12.9%          20.4%   +7.5 pts

That is 28.9% of all races, so promoting the second choice in exactly those
spots is worth roughly +2.2 points on the overall win rate.

Two checks make this trustworthy rather than a curve fit:

  - It holds out of sample. Splitting on date at 2026-07-23: +7.2 pts before,
    +7.7 pts after (n=2,039 held out, p<0.0001).
  - It is not chalk-deferral in disguise. Promoting the favorite is available
    free and wins ~33.9%; pick #2 here wins 20.4%, nowhere near that. So this
    reorders two horses Secretariat already chose rather than surrendering to
    the market.

It is also not a counterfactual estimate. Whether pick #2 won is an observed
fact about a race that already ran — reordering our own labels cannot change it.
"""
import logging
import os

log = logging.getLogger(__name__)

# How much longer than the favorite the top pick must be before its own second
# choice is promoted. The gain rises monotonically with this threshold while the
# number of affected races falls; 2.0 was the best trade of the two.
DEEP_FADE_RATIO = float(os.getenv("DEEP_FADE_RATIO", "2.0"))

# The rule was justified on win rate alone, and win rate was the only thing the
# data could support: the demoted horse's price was never stored, so the ROI
# effect of promoting a shorter-priced second choice was literally unmeasurable.
# Promoting pick #2 takes a shorter price by construction, so a win-rate gain
# can coexist with a money loss. Until that is measured, the rule runs on half
# the eligible races and the other half is left alone as a control.
RERANK_AB_PERCENT = int(os.getenv("RERANK_AB_PERCENT", "50"))


def rerank_arm_for_race(race_id: str) -> str:
    """"on" or "off" for a deep-fade race. Deterministic, own salt."""
    if RERANK_AB_PERCENT >= 100:
        return "on"
    if RERANK_AB_PERCENT <= 0 or not race_id:
        return "off"
    import hashlib
    bucket = int(hashlib.md5(f"rerank:{race_id}".encode()).hexdigest()[:8], 16) % 100
    return "on" if bucket < RERANK_AB_PERCENT else "off"


def should_demote(top_pick_odds, favorite_odds, top_pick_is_favorite) -> bool:
    """Whether this race's top pick is a deep fade that should yield to pick #2."""
    if top_pick_is_favorite:
        return False
    try:
        top, fav = float(top_pick_odds), float(favorite_odds)
    except (TypeError, ValueError):
        return False
    if top <= 0 or fav <= 0:
        return False
    return top / fav >= DEEP_FADE_RATIO


def apply_deep_fade_demotion(analysis: dict, market: dict, race_id: str = "") -> bool:
    """Swap predicted_finish first and second when the top pick is a deep fade.

    Mutates `analysis` in place. Returns True when a swap happened, so callers
    can record it and the effect stays measurable in live results.

    Only the top two slots move: third and fourth are left alone, because the
    measurement only covers the first-versus-second inversion.
    """
    if not analysis or not market:
        return False
    if not should_demote(
        market.get("top_pick_odds"),
        market.get("favorite_odds"),
        market.get("top_pick_is_favorite"),
    ):
        return False
    if rerank_arm_for_race(race_id) != "on":
        return False

    finish = analysis.get("predicted_finish")
    if not isinstance(finish, dict):
        return False
    first, second = finish.get("first"), finish.get("second")
    if not first or not second:
        return False

    finish["first"], finish["second"] = second, first
    log.info(
        "[rerank] demoted deep-fade top pick below its own second choice "
        f"({market.get('top_pick_odds')} vs favorite {market.get('favorite_odds')})"
    )
    return True
