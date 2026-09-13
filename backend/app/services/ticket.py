"""
Secretariat's betting ticket for a race, and how it would have paid.

Everything shown to a user here comes from the official results chart: the win
price from the winning runner and the exotic prices from the race's payoff pools.
Nothing is estimated. A leg we can't price stays "unpriced" rather than being
shown as a win or a loss.

Exotic pools use different base stakes (a $0.50 trifecta, a $0.10 superfecta), so
every payout is restated per $2 to make legs comparable.
"""
from typing import Optional

STAKE = 2.0

# Leg name -> (how many finishers it needs, results-feed wager_type code).
# Win is priced from the winning runner, not the payoff list.
LEGS = (
    ("win", 1, None),
    ("exacta", 2, "E"),
    ("trifecta", 3, "T"),
)


def clean_number(value) -> str:
    """Program numbers compare as trimmed uppercase strings: "1A" stays "1A"."""
    return str(value or "").strip().upper().lstrip("#")


def per_stake(payoff_amount, base_amount, stake: float = STAKE) -> Optional[float]:
    """Restate a pool payout at a common stake. None when it can't be computed."""
    try:
        amount, base = float(payoff_amount), float(base_amount)
    except (TypeError, ValueError):
        return None
    if amount <= 0 or base <= 0:
        return None
    return round(amount / base * stake, 2)


def build_ticket(picks: list[dict], race_number=None) -> list[dict]:
    """Secretariat's legs for one race.

    `picks` is Secretariat's predicted order, each {"name", "number"}. A leg is
    only built when every horse it needs has a program number — telling someone
    to bet a horse without its number is not a bet they can place.
    """
    legs = []
    race = f", race {race_number}" if race_number else ""
    for name, size, _code in LEGS:
        chosen = picks[:size]
        if len(chosen) < size or not all(clean_number(p.get("number")) for p in chosen):
            continue
        numbers = [clean_number(p["number"]) for p in chosen]
        if name == "win":
            say = f"${STAKE:.0f} to win on #{numbers[0]}{race}"
        else:
            say = f"${STAKE:.0f} {name} {'-'.join(numbers)}{race}"
        legs.append({
            "type": name,
            "numbers": numbers,
            "horses": [p.get("name", "") for p in chosen],
            "say": say,
            "status": "pending",
            "payout": None,
            "winning_numbers": None,
        })
    return legs


def grade_ticket(legs: list[dict], result: dict) -> list[dict]:
    """Mark each leg hit, miss or unpriced from the official result.

    `result` is one race from the results feed: `runners` in finish order and a
    `payoffs` list of exotic pools.
    """
    runners = result.get("runners") or []
    if not runners:
        return legs

    winner = runners[0]
    winner_number = clean_number(winner.get("program_number"))
    payoffs = {p.get("wager_type"): p for p in (result.get("payoffs") or [])}

    graded = []
    for leg in legs:
        leg = dict(leg)
        if leg["type"] == "win":
            leg["winning_numbers"] = [winner_number] if winner_number else None
            hit = bool(winner_number) and leg["numbers"][0] == winner_number
            price = per_stake(winner.get("win_payoff"), STAKE) if hit else None
            if hit and price is None:
                leg["status"] = "unpriced"
            else:
                leg["status"] = "hit" if hit else "miss"
                leg["payout"] = price
        else:
            code = next(c for n, _s, c in LEGS if n == leg["type"])
            pool = payoffs.get(code)
            if not pool:
                # This race had no such pool, or the chart doesn't carry it.
                leg["status"] = "unpriced"
            else:
                winning = [clean_number(n) for n in str(pool.get("winning_numbers") or "").split("-") if n]
                leg["winning_numbers"] = winning or None
                hit = winning == leg["numbers"]
                leg["status"] = "hit" if hit else "miss"
                leg["payout"] = per_stake(pool.get("payoff_amount"), pool.get("base_amount")) if hit else None
        graded.append(leg)
    return graded


def ticket_summary(legs: list[dict]) -> dict:
    """Staked vs returned across the priced legs, for the one-line result."""
    priced = [l for l in legs if l["status"] in ("hit", "miss")]
    staked = STAKE * len(priced)
    returned = sum(l["payout"] or 0 for l in priced if l["status"] == "hit")
    return {
        "legs_priced": len(priced),
        "hits": sum(1 for l in priced if l["status"] == "hit"),
        "staked": round(staked, 2),
        "returned": round(returned, 2),
        "net": round(returned - staked, 2),
    }
