#!/usr/bin/env python3
"""
backfill_form.py — Seed horse form lines from past results.

Form only becomes useful once there's history, so pull whatever the results
feed still serves for recent dates rather than waiting weeks from zero.
Idempotent: re-running adds nothing for races already recorded.

Usage:
    cd backend
    python scripts/backfill_form.py --days 60
    python scripts/backfill_form.py --days 14 --dry-run
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


async def main(days: int, dry_run: bool):
    from app.core import database as _db
    from app.services.horse_form import extract_form_rows, record_race_form
    from app.services.racing_api import get_na_results_full

    await _db.init_db()

    today = datetime.date.today()
    dates = [today - datetime.timedelta(days=i) for i in range(1, days + 1)]
    total_rows = 0
    total_races = 0
    for d in sorted(dates):
        try:
            data = await get_na_results_full(d.isoformat())
        except Exception as e:
            print(f"  {d}: results fetch failed ({e})")
            continue
        results = data.get("results", []) or []
        if not results:
            print(f"  {d}: no results")
            continue
        rows = 0
        for res in results:
            if dry_run:
                rows += len(extract_form_rows(res, d))
            else:
                rows += await record_race_form(res, d)
        total_rows += rows
        total_races += len(results)
        print(f"  {d}: {len(results)} races -> {rows} form lines"
              + (" [dry-run]" if dry_run else ""))

    print(f"\n{'Would add' if dry_run else 'Added'} {total_rows} form lines "
          f"from {total_races} races across {days} days.")

    if not dry_run:
        from sqlalchemy import text as _t
        async with _db._AsyncSessionLocal() as db:
            horses = (await db.execute(_t("SELECT COUNT(DISTINCT horse_key) FROM horse_form_lines"))).scalar()
            lines = (await db.execute(_t("SELECT COUNT(*) FROM horse_form_lines"))).scalar()
            multi = (await db.execute(_t(
                "SELECT COUNT(*) FROM (SELECT horse_key FROM horse_form_lines "
                "GROUP BY horse_key HAVING COUNT(*) > 1) x"))).scalar()
        print(f"Archive now: {lines} lines across {horses} horses "
              f"({multi} with 2+ starts recorded).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill horse form lines from results")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.days, a.dry_run))
