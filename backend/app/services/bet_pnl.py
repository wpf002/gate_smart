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

    Returns {"win", "place", "show"} in dollars per $2 staked, or None when the
    chart carries no usable payoffs yet (caller must exclude the race).

    Within the dict, the two values mean different things:
        0.0   the bet was available and lost
        None  that pool wasn't offered, so the bet could not have been placed

    Small fields frequently have no show pool (and sometimes no place pool).
    The winner's own payoffs reveal which pools existed — a winner always
    collects from every pool that ran — so a missing pool is never mistaken for
    a losing bet, which would invent losses that were impossible to incur.
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

    has_place_pool = _f(winner.get("place_payoff")) > 0
    has_show_pool = _f(winner.get("show_payoff")) > 0

    target = _norm(pick_name)
    for r in runners:
        if _norm(r.get("horse_name") or r.get("horse")) == target:
            return {
                "win": _f(r.get("win_payoff")),
                "place": _f(r.get("place_payoff")) if has_place_pool else None,
                "show": _f(r.get("show_payoff")) if has_show_pool else None,
            }
    # Priced chart, but our pick ran off the board (charts list only the top 3):
    # every bet that existed lost, which is a real, known outcome.
    return {
        "win": 0.0,
        "place": 0.0 if has_place_pool else None,
        "show": 0.0 if has_show_pool else None,
    }


def compute_flat_bet_pnl(rows: list, stake: float = STAKE) -> dict:
    """Aggregate $`stake` flat-bet performance over races with real payoffs.

    `rows` are objects/dicts exposing top_pick_win_payoff / _place_ / _show_.
    Rows without payoff data are skipped and reported via `unpriced_races`, so
    the ROI denominator only covers bets we can actually price.

    Each strategy carries the two numbers that say whether it can ever pay:
    `hit_rate`, how often the bet cashed, and `breakeven_rate`, the hit rate it
    would have needed at the prices those bets actually paid. Their difference
    is the whole question — a strategy makes money only once hit_rate passes
    breakeven_rate, and no amount of staking changes that.

    across_the_board (win + place + show on the same horse) is still computed
    because the stored daily series has its columns, but it is not a strategy
    anyone should follow: it stakes 3x into the three worst-priced pools at once.
    """
    mult = stake / STAKE  # payoffs are quoted per $2

    def _get(row, attr):
        return row.get(attr) if isinstance(row, dict) else getattr(row, attr, None)

    priced = [r for r in rows if _get(r, "top_pick_win_payoff") is not None]
    n = len(priced)

    # A None place/show payoff means that pool wasn't offered, so no stake could
    # have been placed. Only count stakes for pools that actually ran.
    pools = {
        "win": priced,
        "place": [r for r in priced if _get(r, "top_pick_place_payoff") is not None],
        "show": [r for r in priced if _get(r, "top_pick_show_payoff") is not None],
    }
    returned = {
        name: sum(_f(_get(r, f"top_pick_{name}_payoff")) for r in rs) * mult
        for name, rs in pools.items()
    }

    # How often a name pulled out of the hat would have cashed the same bet in
    # the same races: 1 winner, 2 place spots and 3 show spots per field. It is
    # the only baseline available from our own rows, and it's what separates
    # "the picks are wrong" from "the picks are right and the price is dearer".
    depth = {"win": 1, "place": 2, "show": 3}

    def _random_rate(rs, places):
        sized = [_get(r, "field_size") for r in rs]
        sized = [int(f) for f in sized if f and int(f) > 1]
        if not sized:
            return None
        return sum(min(places / f, 1.0) for f in sized) / len(sized)

    def _pack(staked, ret, rs=None, field=None, name=None):
        net = ret - staked
        out = {
            "staked": round(staked, 2),
            "returned": round(ret, 2),
            "net": round(net, 2),
            "roi": round(net / staked, 4) if staked else 0.0,
        }
        if rs is not None:
            cashed = [_f(_get(r, field)) for r in rs if _f(_get(r, field)) > 0]
            avg = (sum(cashed) / len(cashed)) if cashed else 0.0
            hit = (len(cashed) / len(rs)) if rs else None
            rand = _random_rate(rs, depth.get(name, 1))
            out.update({
                "bets": len(rs),
                "cashed": len(cashed),
                "hit_rate": round(hit, 4) if hit is not None else None,
                "avg_payoff": round(avg, 2),
                # What fraction of these bets had to cash to get the money back.
                "breakeven_rate": round(STAKE / avg, 4) if avg else None,
                "random_rate": round(rand, 4) if rand is not None else None,
                "lift": round(hit / rand, 2) if hit is not None and rand else None,
            })
            if out["hit_rate"] is not None and out["breakeven_rate"] is not None:
                out["gap"] = round(out["hit_rate"] - out["breakeven_rate"], 4)
        return out

    result = {
        "races": n,
        "unpriced_races": len(rows) - n,
        "stake": stake,
    }
    for name, rs in pools.items():
        result[name] = _pack(len(rs) * stake, returned[name], rs, f"top_pick_{name}_payoff", name)
    result["across_the_board"] = _pack(
        sum(len(rs) for rs in pools.values()) * stake, sum(returned.values())
    )
    return result
