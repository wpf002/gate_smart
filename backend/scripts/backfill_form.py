#!/usr/bin/env python3
"""
backfill_form.py — Seed horse form lines from past results.

Form only becomes useful once there's history, so pull whatever the results
feed still serves rather than waiting weeks from zero.

Built to survive a long run: dates already recorded are skipped, and a
transient failure (DNS blip, dropped DB connection, upstream 5xx) retries and
then moves on instead of killing hours of work. Re-running resumes where it
left off and costs nothing for dates already done.

Usage:
    cd backend
    python scripts/backfill_form.py --days 60
    python scripts/backfill_form.py --since 2024-01-01
    python scripts/backfill_form.py --since 2024-01-01 --dry-run
    python scripts/backfill_form.py --since 2024-01-01 --redo   # ignore coverage
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

RETRIES = 3
RETRY_SLEEP = 5


async def _covered_dates() -> set:
    """Dates that already have form lines — skipped so re-runs are cheap."""
    from sqlalchemy import text as T

    from app.core import database as _db
    try:
        async with _db._AsyncSessionLocal() as db:
            rows = (await db.execute(T("SELECT DISTINCT race_date FROM horse_form_lines"))).all()
        return {r[0] for r in rows if r[0]}
    except Exception:
        return set()


async def _process_date(d, dry_run: bool) -> int:
    """Record one date's results. Retries transient failures before giving up."""
    from app.services.horse_form import extract_form_rows, record_many_races
    from app.services.racing_api import get_na_results_full

    last_err = None
    for attempt in range(RETRIES):
        try:
            data = await get_na_results_full(d.isoformat())
            results = data.get("results", []) or []
            if not results:
                return 0
            if dry_run:
                return sum(len(extract_form_rows(res, d)) for res in results)
            # One statement per day rather than one per race — the write, not
            # the fetch, was the bottleneck.
            return await record_many_races(results, d)
        except Exception as e:  # DNS blips, dropped pools, upstream 5xx
            last_err = e
            if attempt < RETRIES - 1:
                await asyncio.sleep(RETRY_SLEEP * (attempt + 1))
    raise RuntimeError(f"{d}: gave up after {RETRIES} attempts ({last_err})")


async def main(dates: list, dry_run: bool, redo: bool):
    from app.core import database as _db
    await _db.init_db()
    # Bulk job: throttle upstream calls. Live request handlers must not,
    # or a fan-out request stalls behind the pacing lock.
    from app.services.racing_api import set_bulk_mode
    set_bulk_mode(True)

    covered = set() if redo else await _covered_dates()
    todo = [d for d in dates if d not in covered]
    print(f"[backfill_form] {len(dates)} dates in range | {len(dates)-len(todo)} already recorded "
          f"| {len(todo)} to process\n")

    total_rows = 0
    failed = []
    for i, d in enumerate(todo, 1):
        try:
            rows = await _process_date(d, dry_run)
            total_rows += rows
            if i % 10 == 0 or rows == 0:
                print(f"  [{i}/{len(todo)}] {d}: {rows} lines (running total {total_rows})", flush=True)
        except Exception as e:
            failed.append(d)
            print(f"  [{i}/{len(todo)}] {d}: FAILED — {e}", flush=True)

    print(f"\n{'Would add' if dry_run else 'Added'} {total_rows} form lines.")
    if failed:
        print(f"{len(failed)} dates failed and were skipped; re-run to retry them: "
              f"{failed[0]} .. {failed[-1]}")

    if not dry_run:
        from sqlalchemy import text as T
        async with _db._AsyncSessionLocal() as db:
            lines = (await db.execute(T("SELECT COUNT(*) FROM horse_form_lines"))).scalar()
            horses = (await db.execute(T("SELECT COUNT(DISTINCT horse_key) FROM horse_form_lines"))).scalar()
            multi = (await db.execute(T(
                "SELECT COUNT(*) FROM (SELECT horse_key FROM horse_form_lines "
                "GROUP BY horse_key HAVING COUNT(*) >= 3) x"))).scalar()
        print(f"Archive now: {lines} lines / {horses} horses ({multi} with 3+ starts).")

        # Integrity gate. A string `also_ran` iterated as characters once wrote
        # 517k single-letter "horses" and inflated field_size on every real
        # runner in those races — and nothing failed, so it went unnoticed for
        # hours. Fail loudly rather than bank corrupt history again.
        async with _db._AsyncSessionLocal() as db:
            # Single-character names are the signature of the character-split
            # bug. Two-character names are NOT corruption — "Jr", "Oh" and "Oz"
            # are real horses in the feed, and an earlier version of this check
            # failed a good run on them.
            junk = (await db.execute(T(
                "SELECT COUNT(*) FROM horse_form_lines WHERE LENGTH(horse_key) < 2"))).scalar()
            huge = (await db.execute(T(
                "SELECT COUNT(*) FROM horse_form_lines WHERE field_size > 30"))).scalar()
        if junk or huge:
            print(f"\n!! INTEGRITY FAILURE: {junk} single-character names, "
                  f"{huge} rows with field_size > 30. Purge the affected races and "
                  f"re-run with --dates-file before trusting this archive.")
            sys.exit(1)
        print("Integrity OK: no malformed names, no impossible field sizes.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill horse form lines from results")
    ap.add_argument("--days", type=int, default=30, help="days back from yesterday")
    ap.add_argument("--since", type=str, default=None, help="YYYY-MM-DD; overrides --days")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--redo", action="store_true", help="re-process dates already recorded")
    ap.add_argument("--dates-file", type=str, default=None,
                    help="file of YYYY-MM-DD lines to repair; implies --redo. Use after purging "
                         "bad rows, where a date keeps some rows and would otherwise look covered.")
    a = ap.parse_args()

    today = datetime.date.today()
    if a.dates_file:
        dates = [datetime.date.fromisoformat(x.strip())
                 for x in open(a.dates_file) if x.strip()]
        a.redo = True  # a partially-purged date still looks covered
    elif a.since:
        start = datetime.date.fromisoformat(a.since)
        span = (today - start).days
        dates = [start + datetime.timedelta(days=i) for i in range(span)]
    else:
        dates = sorted(today - datetime.timedelta(days=i) for i in range(1, a.days + 1))

    asyncio.run(main(dates, a.dry_run, a.redo))
