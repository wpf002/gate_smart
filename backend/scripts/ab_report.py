#!/usr/bin/env python3
"""
ab_report.py — Score the pick-engine model A/B on identical races.

Both arms run the same slate on the same days, so the comparison is like-for-like.
Reports the metric the experiment exists to move — how often the #1 pick actually
wins — plus ITM and real flat-bet ROI from official payoffs, and a significance
check so a few lucky days don't get read as a result.

Usage:
    cd backend
    python scripts/ab_report.py
    python scripts/ab_report.py --days 30
"""
import argparse
import asyncio
import datetime
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — honest small-sample bounds on a win rate."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def _two_proportion_p(w1: int, n1: int, w2: int, n2: int) -> float | None:
    """Two-sided p-value for the difference in two win rates (normal approx)."""
    if n1 < 30 or n2 < 30:
        return None
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    z = abs(p1 - p2) / se
    # two-sided normal tail
    return math.erfc(z / math.sqrt(2))


async def main(days: int):
    from sqlalchemy import text as _text

    from app.core import database as _db
    await _db.init_db()

    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(_text("""
            SELECT pick_model,
                   COUNT(*)                                        AS n,
                   SUM((top_pick_correct)::int)                    AS wins,
                   SUM((in_the_money)::int)                        AS itm,
                   COUNT(top_pick_win_payoff)                      AS priced,
                   COALESCE(SUM(top_pick_win_payoff), 0)           AS returned,
                   SUM((top_pick_is_favorite)::int)                AS faved
            FROM race_predictions
            WHERE race_date >= :cutoff
              AND pick_model IS NOT NULL
              AND analysis_mode = 'auto_daily' AND user_id IS NULL
              AND result_fetched AND actual_first IS NOT NULL AND actual_first <> ''
            GROUP BY pick_model ORDER BY pick_model
        """), {"cutoff": cutoff})).all()

    if not rows:
        print(f"No settled A/B races in the last {days} days yet.")
        print("Picks carry pick_model from the next nightly run; results settle the morning after.")
        return

    print(f"\nPICK-ENGINE A/B — last {days} days, settled races only\n")
    print(f"{'model':32} {'races':>6} {'win%':>7} {'95% CI':>16} {'ITM%':>7} {'ROI':>8} {'fav%':>6}")
    stats = {}
    for r in rows:
        n, wins = r.n, int(r.wins or 0)
        lo, hi = _wilson(wins, n)
        priced, returned = int(r.priced or 0), float(r.returned or 0)
        roi = ((returned - 2 * priced) / (2 * priced)) if priced else None
        stats[r.pick_model] = (wins, n)
        roi_s = f"{roi:+.1%}" if roi is not None else "n/a"
        print(f"{(r.pick_model or '?')[:32]:32} {n:>6} {wins/n:>6.1%} "
              f"{f'[{lo:.1%}-{hi:.1%}]':>16} {int(r.itm or 0)/n:>6.1%} {roi_s:>8} "
              f"{int(r.faved or 0)/n:>5.0%}")

    if len(stats) == 2:
        (m1, (w1, n1)), (m2, (w2, n2)) = stats.items()
        p = _two_proportion_p(w1, n1, w2, n2)
        diff = (w2 / n2) - (w1 / n1)
        print(f"\n  difference ({m2} - {m1}): {diff:+.1f} pts" if False else
              f"\n  difference: {m2} minus {m1} = {diff*100:+.1f} points")
        if p is None:
            print("  Too few races for a significance test (need 30+ per arm). Keep it running.")
        elif p < 0.05:
            print(f"  p = {p:.3f} — statistically significant at 95%.")
        else:
            print(f"  p = {p:.3f} — NOT significant. This is still noise; keep it running.")
        print("\n  Reminder: win rate is the target, but check ROI too — a model that "
              "wins more by\n  taking shorter prices can still make less money.")
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score the pick-engine model A/B")
    ap.add_argument("--days", type=int, default=14)
    asyncio.run(main(ap.parse_args().days))
