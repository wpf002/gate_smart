#!/usr/bin/env python3
"""
Utility: reset settled predictions for a given date back to unsettled.
Use before re-running nightly_accuracy.py on a date that was already processed.

Usage:
    python scripts/reset_date_predictions.py --date 2026-04-18
    python scripts/reset_date_predictions.py --date 2026-04-18 --dry-run
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


async def main(target_date: datetime.date, dry_run: bool):
    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from sqlalchemy import update, select

    await _db.init_db()

    async with _db._AsyncSessionLocal() as db:
        count_res = await db.execute(
            select(RacePrediction).where(RacePrediction.race_date == target_date)
        )
        rows = count_res.scalars().all()
        print(f"Found {len(rows)} predictions for {target_date}")

        if dry_run:
            print("[DRY RUN] No rows modified.")
            return

        result = await db.execute(
            update(RacePrediction)
            .where(RacePrediction.race_date == target_date)
            .values(
                result_fetched=False,
                actual_first=None,
                actual_second=None,
                actual_third=None,
                top_pick_correct=False,
                in_the_money=False,
                settled_at=None,
            )
        )
        await db.commit()
        print(f"Reset {result.rowcount} rows to unsettled.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset settled predictions for re-processing")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(datetime.date.fromisoformat(args.date), args.dry_run))
