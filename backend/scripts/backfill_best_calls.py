#!/usr/bin/env python3
"""
backfill_best_calls.py — Recompute best_call / worst_miss on recent daily reports.

nightly_accuracy used `max(..., key=lambda s: 1)`, which returns the first row,
so every stored "Best Call" was simply the first winner settled that day. This
rewrites recent reports with the same best_and_worst() the nightly job now uses:
best = winning pick with the highest official $2 win payoff, worst = the
shortest-priced pick that lost. Only those two text fields change.

Usage:
    cd backend
    python scripts/backfill_best_calls.py --days 30 --dry-run
    python scripts/backfill_best_calls.py --days 30
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


async def main(days: int, dry_run: bool) -> None:
    from sqlalchemy import desc, select

    from app.core import database as _db
    from app.models.accuracy import DailyAccuracyReport, RacePrediction
    from scripts.nightly_accuracy import best_and_worst

    await _db.init_db()
    changed = 0
    async with _db._AsyncSessionLocal() as db:
        reports = (await db.execute(
            select(DailyAccuracyReport).order_by(desc(DailyAccuracyReport.report_date)).limit(days)
        )).scalars().all()
        for report in reports:
            # Same rows the nightly report scores: Secretariat's slate, settled,
            # with a recorded winner.
            preds = (await db.execute(select(RacePrediction).where(
                RacePrediction.race_date == report.report_date,
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.user_id.is_(None),
                RacePrediction.result_fetched == True,  # noqa: E712
                RacePrediction.actual_first.isnot(None),
            ))).scalars().all()
            rows = [{
                "race_id": p.race_id, "race_name": p.race_name,
                "predicted": p.predicted_first, "actual": p.actual_first,
                "top_correct": bool(p.top_pick_correct),
                "top_pick_win_payoff": p.top_pick_win_payoff, "top_pick_odds": p.top_pick_odds,
            } for p in preds]
            best, worst = best_and_worst(rows)
            if (best, worst) != (report.best_call, report.worst_miss):
                changed += 1
            print(f"{report.report_date}  best: {best}\n            was:  {report.best_call}")
            if not dry_run:
                report.best_call, report.worst_miss = best, worst
        if not dry_run:
            await db.commit()
    print(f"\n{'Would change' if dry_run else 'Changed'} {changed} of {len(reports)} reports.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Recompute best call / worst miss on daily reports")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.days, a.dry_run))
