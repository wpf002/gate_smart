#!/usr/bin/env python3
"""
depth_report.py — Is the cheap pick as good as the expensive one?

A full analysis costs ~$0.037 a race and writes ~3,470 output tokens; the
lightweight predict path costs ~$0.001 and writes ~40. Output is ~70% of the
bill. If the cheap path locks an equally accurate PICK, the write-up only needs
generating when someone opens the race — /analyze already does that on a cache
miss — and the nightly bill falls by roughly 70%.

If it does not, this stays at zero and we keep paying. That is the whole point
of measuring rather than assuming.

Usage:
    cd backend
    python scripts/depth_report.py --days 21
"""
import argparse
import asyncio
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

FULL_COST, LEAN_COST = 0.037, 0.001


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
    from scripts.score_lessons import two_proportion_p

    await _db.init_db()
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(T(f"""
            SELECT lock_source, COUNT(*) n,
                   SUM(CASE WHEN top_pick_correct THEN 1 ELSE 0 END) w,
                   SUM(CASE WHEN in_the_money THEN 1 ELSE 0 END) itm
            FROM race_predictions
            WHERE result_fetched AND analysis_mode = 'auto_daily' AND user_id IS NULL
              AND lock_source IN ('nightly', 'nightly_lean')
              AND race_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
            GROUP BY 1
        """))).all()

    stats = {r[0]: (r[2], r[1], r[3]) for r in rows}
    print("=" * 70)
    print(f"PICK DEPTH — full analysis vs cheap predict (last {days} days)")
    print("=" * 70)
    if not stats:
        print("\nNo races yet. The split starts with the next nightly slate.")
        return

    print(f"\n{'arm':<16}{'races':>7}{'win':>8}{'95% CI':>18}{'ITM':>8}")
    for key, label in (("nightly", "full"), ("nightly_lean", "lean")):
        if key not in stats:
            continue
        w, n, itm = stats[key]
        lo, hi = wilson(w, n)
        print(f"{label:<16}{n:>7}{w/n:>7.1%}{f'[{lo:.0%}–{hi:.0%}]':>18}{itm/n:>7.1%}")

    if "nightly" in stats and "nightly_lean" in stats:
        (fw, fn, _), (lw, ln, _) = stats["nightly"], stats["nightly_lean"]
        diff = 100.0 * (lw / ln - fw / fn)
        p = two_proportion_p(lw, ln, fw, fn)
        print(f"\nlean minus full: {diff:+.1f} points" + (f", p={p:.3f}" if p else ""))

        # What the swap would be worth if the picks really are equivalent.
        daily = (fn + ln) / max(days, 1)
        saving = daily * (FULL_COST - LEAN_COST) * 30
        print(f"If equivalent, going all-lean saves roughly ${saving:.0f}/month "
              f"at {daily:.0f} races/day.")

        if ln < 300:
            print(f"\nToo early: {ln} lean races. Want 300+ before reading this, and even")
            print("then only a LARGE gap is detectable — a 2-3 point difference needs "
                  "thousands.")
        elif p is not None and p < 0.05 and diff < 0:
            print("\nThe cheap pick is measurably worse. Keep paying for the full analysis.")
        elif p is not None and p >= 0.05:
            print("\nNo detectable difference so far. Absence of a gap at this sample size")
            print("is not proof they are equal — check the CI overlap before switching.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Compare pick accuracy by analysis depth")
    ap.add_argument("--days", type=int, default=21)
    asyncio.run(main(ap.parse_args().days))
