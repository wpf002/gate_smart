"""
Restating a pool payout at a common stake.

Exotic pools are quoted at different base stakes (a $0.50 trifecta, a $0.10
superfecta), so nothing is comparable until it's restated per $2 — the US track
minimum, and the base win/place/show payoffs are already quoted at.

Everything priced through here comes from the official results chart. A pool the
chart doesn't carry returns None, so the caller can mark the bet unpriced rather
than scoring it as a loss.
"""
from typing import Optional

STAKE = 2.0


def per_stake(payoff_amount, base_amount, stake: float = STAKE) -> Optional[float]:
    """Restate a pool payout at a common stake. None when it can't be computed."""
    try:
        amount, base = float(payoff_amount), float(base_amount)
    except (TypeError, ValueError):
        return None
    if amount <= 0 or base <= 0:
        return None
    return round(amount / base * stake, 2)
