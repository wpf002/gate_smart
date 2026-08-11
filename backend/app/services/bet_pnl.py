"""
Flat-bet P&L from OFFICIAL results-chart payoffs.

US payoffs are quoted per $2 wagered (the classic $2.10 minimum show payoff
confirms the base), so a $2 bet returns the payoff figure as-is.

Nothing here estimates or models a price: if the chart has no payoff for a race
we mark it unpriced and exclude it from the denominator, rather than assuming a
loss. Morning-line odds are deliberately never used — they are not the price the
bet would actually have been settled at.
"""

STAKE = 2.0  # the standard US track minimum, and the payoff quoting base


def _norm(name: str) -> str:
    return (name or "").lower().strip().replace("'", "").replace("-", " ")


def _f(v) -> float:
    try:
        f = float(v)
        return f if f > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def extract_top_pick_payoffs(race_result: dict, pick_name: str) -> dict | None:
    """Payoffs our top pick actually returned in this race.

    Returns {"win", "place", "show"} in dollars per $2 staked (0.0 where the
    pick earned nothing), or None when the chart carries no usable payoffs yet —
    the caller must then exclude the race rather than score it as a loss.
    """
    runners = (race_result or {}).get("runners") or []
    if not runners or not pick_name:
        return None

    # A chart is "priced" once the winner has a real win payoff. Without that the
    # payoff columns simply haven't been published yet.
    winner = next(
        (r for r in runners if str(r.get("position") or r.get("finish_position") or "") == "1"),
        runners[0] if runners else None,
    )
    if not winner or _f(winner.get("win_payoff")) <= 0:
        return None

    target = _norm(pick_name)
    for r in runners:
        if _norm(r.get("horse_name") or r.get("horse")) == target:
            return {
                "win": _f(r.get("win_payoff")),
                "place": _f(r.get("place_payoff")),
                "show": _f(r.get("show_payoff")),
            }
    # Priced chart, but our pick ran off the board (charts list only the top 3):
    # every bet on it lost, which is a real, known outcome.
    return {"win": 0.0, "place": 0.0, "show": 0.0}


def compute_flat_bet_pnl(rows: list, stake: float = STAKE) -> dict:
    """Aggregate $`stake` flat-bet performance over races with real payoffs.

    `rows` are objects/dicts exposing top_pick_win_payoff / _place_ / _show_.
    Rows without payoff data are skipped and reported via `unpriced_races`, so
    the ROI denominator only covers bets we can actually price.

    Two strategies:
      win — $stake to win on every top pick
      atb — "across the board": $stake each to win, place and show (3x staked)
    """
    mult = stake / STAKE  # payoffs are quoted per $2

    def _get(row, attr):
        return row.get(attr) if isinstance(row, dict) else getattr(row, attr, None)

    priced = [r for r in rows if _get(r, "top_pick_win_payoff") is not None]
    n = len(priced)

    win_returned = sum(_f(_get(r, "top_pick_win_payoff")) for r in priced) * mult
    place_returned = sum(_f(_get(r, "top_pick_place_payoff")) for r in priced) * mult
    show_returned = sum(_f(_get(r, "top_pick_show_payoff")) for r in priced) * mult

    win_staked = n * stake
    atb_staked = n * stake * 3
    atb_returned = win_returned + place_returned + show_returned

    def _pack(staked, returned):
        net = returned - staked
        return {
            "staked": round(staked, 2),
            "returned": round(returned, 2),
            "net": round(net, 2),
            "roi": round(net / staked, 4) if staked else 0.0,
        }

    return {
        "races": n,
        "unpriced_races": len(rows) - n,
        "stake": stake,
        "win": _pack(win_staked, win_returned),
        "across_the_board": _pack(atb_staked, atb_returned),
    }
