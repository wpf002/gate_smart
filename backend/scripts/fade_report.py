#!/usr/bin/env python3
"""
fade_report.py — Which fades are worth making.

Siding with the morning-line favorite wins ~34%; fading wins ~17%. Fading is not
the problem by itself — an all-favorites card wins 34% and returns nothing at
those prices. The problem is that every fade counted the same, so there was no
way to tell a lone-speed read from a hunch.

Each fade now names its angle. This scores them against two baselines that
matter: the agree rate (what siding with the market would have paid) and the
overall fade rate. A reason beating the fade average is one to lean into; a
reason below it is a habit to drop.

Usage:
    cd backend
    python scripts/fade_report.py --days 30
"""
import argparse
import asyncio
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def wilson(w: int, n: int) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    z, p = 1.96, w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


async def main(days: int) -> None:
    from sqlalchemy import text as T

    from app.core import database as _db
    from app.services.fade_reason import FADE_REASONS, NO_FADE, UNSPECIFIED

    await _db.init_db()
    base = ("result_fetched AND analysis_mode = 'auto_daily' AND user_id IS NULL "
            f"AND race_date >= CURRENT_DATE - INTERVAL '{int(days)} days'")

    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(T(f"""
            SELECT COALESCE(fade_reason, 'not_recorded') reason, COUNT(*) n,
                   SUM(CASE WHEN top_pick_correct THEN 1 ELSE 0 END) w,
                   AVG(top_pick_win_payoff) avg_payoff,
                   SUM(COALESCE(top_pick_win_payoff, 0)) ret,
                   COUNT(*) FILTER (WHERE top_pick_win_payoff IS NOT NULL) priced
            FROM race_predictions WHERE {base} AND fade_reason IS NOT NULL
            GROUP BY 1 ORDER BY n DESC
        """))).all()

    if not rows:
        print("No races carry a fade reason yet.")
        print("Picks record one from the next nightly slate; results settle the morning after.")
        return

    by = {r[0]: r for r in rows}
    agree = by.get(NO_FADE)
    fades = [r for r in rows if r[0] not in (NO_FADE, "not_recorded")]
    f_n = sum(r[1] for r in fades)
    f_w = sum(r[2] for r in fades)

    print("=" * 76)
    print(f"FADE SCORECARD — last {days} days")
    print("=" * 76)
    if agree:
        print(f"\nSided with the favorite : {agree[2]}/{agree[1]} = {agree[2]/agree[1]:.1%}")
    if f_n:
        print(f"Faded the favorite      : {f_w}/{f_n} = {f_w/f_n:.1%}"
              f"  ({f_n/(f_n + (agree[1] if agree else 0)):.0%} of races)")

    fade_rate = f_w / f_n if f_n else 0.0
    print(f"\n{'reason':<18}{'races':>7}{'win':>8}{'95% CI':>18}{'vs fade avg':>13}{'$2 ROI':>9}")
    for reason, n, w, avg_payoff, ret, priced in sorted(fades, key=lambda r: -(r[2] / r[1] if r[1] else 0)):
        lo, hi = wilson(w, n)
        delta = 100.0 * (w / n - fade_rate)
        roi = (ret - 2 * priced) / (2 * priced) if priced else None
        print(f"{reason:<18}{n:>7}{w/n:>7.1%}{f'[{lo:.0%}–{hi:.0%}]':>18}"
              f"{delta:>+12.1f}{(f'{roi:>+8.0%}' if roi is not None else '       —')}")

    unspec = by.get(UNSPECIFIED)
    if unspec and f_n:
        print(f"\n{unspec[1]} fades ({unspec[1]/f_n:.0%}) named no reason in the vocabulary.")
        print("Those are the ones to cut first — the prompt asks for a specific angle,")
        print("and 'unspecified' means the model diverged without one.")

    thin = [r for r in fades if r[1] < 50]
    if thin:
        print(f"\n{len(thin)} reason(s) under 50 races — {', '.join(r[0] for r in thin)}. "
              f"Read those as provisional.")
    print(f"\nKnown reasons: {', '.join(FADE_REASONS)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Score Secretariat's fades by stated reason")
    ap.add_argument("--days", type=int, default=30)
    asyncio.run(main(ap.parse_args().days))
