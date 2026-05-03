#!/usr/bin/env python3
"""verify_accuracy.py — Verify the rolling-100 win rate against actual DB rows.

Run with: railway run python backend/scripts/verify_accuracy.py

Reports total rows, last-100 breakdown, date range, and a sample of the
most recent picks so we can sanity-check the badge against ground truth.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from sqlalchemy import select, func

    await _db.init_db()

    async with _db._AsyncSessionLocal() as db:
        total_count = await db.execute(
            select(func.count())
            .select_from(RacePrediction)
            .where(
                RacePrediction.result_fetched.is_(True),
                RacePrediction.user_id.is_(None),
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.top_pick_correct.is_not(None),
            )
        )
        total_with_outcome = total_count.scalar()

        result = await db.execute(
            select(
                RacePrediction.race_id,
                RacePrediction.race_date,
                RacePrediction.track_code,
                RacePrediction.predicted_first,
                RacePrediction.actual_first,
                RacePrediction.top_pick_correct,
                RacePrediction.settled_at,
            )
            .where(
                RacePrediction.result_fetched.is_(True),
                RacePrediction.user_id.is_(None),
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.top_pick_correct.is_not(None),
            )
            .order_by(RacePrediction.settled_at.desc().nulls_last())
            .limit(100)
        )
        rows = result.all()

    n = len(rows)
    wins = sum(1 for r in rows if r.top_pick_correct)
    losses = n - wins
    win_rate = (wins / n * 100) if n else 0

    print()
    print("=" * 72)
    print("  ROLLING-100 ACCURACY VERIFICATION")
    print("=" * 72)
    print(f"  Total rows with outcome data in DB: {total_with_outcome}")
    print(f"  Last-100 sample size: {n}")
    print(f"  Wins (top pick finished 1st): {wins}")
    print(f"  Misses: {losses}")
    print(f"  Win rate: {win_rate:.1f}%")
    if rows:
        oldest = rows[-1].race_date
        newest = rows[0].race_date
        print(f"  Date range covered: {oldest} -> {newest}")
        print()
        print("  Most recent 15 settled picks:")
        print("  " + "-" * 70)
        for r in rows[:15]:
            mark = "WIN " if r.top_pick_correct else "miss"
            track = (r.track_code or "?")[:5]
            picked = (r.predicted_first or "?")[:24]
            actual = (r.actual_first or "?")[:24]
            print(f"  [{mark}] {r.race_date} {track:<5} picked: {picked:<24}  actual: {actual}")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
