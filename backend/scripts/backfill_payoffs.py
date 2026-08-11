#!/usr/bin/env python3
"""
backfill_payoffs.py — Fill in official top-pick payoffs for already-settled
races so flat-bet P&L can be reported for past days.

Payoffs come straight from the results chart; nothing is estimated. Races whose
chart carries no payoff are left NULL so they stay excluded from ROI rather than
being scored as losses. Re-runnable: only rows missing a payoff are touched
(pass --force to re-read rows that already have one).

Usage:
    cd backend
    python scripts/backfill_payoffs.py --days 14
    python scripts/backfill_payoffs.py --date 2026-08-10
    python scripts/backfill_payoffs.py --days 14 --dry-run
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


async def backfill_date(target: datetime.date, dry_run: bool, force: bool) -> tuple[int, int]:
    from sqlalchemy import select

    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from app.services.bet_pnl import compute_flat_bet_pnl, extract_top_pick_payoffs
    from app.services.racing_api import get_na_results_full

    async with _db._AsyncSessionLocal() as db:
        rows = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date == target,
                RacePrediction.result_fetched == True,  # noqa: E712
                RacePrediction.analysis_mode == "auto_daily",
                RacePrediction.user_id.is_(None),
            )
        )
        preds = list(rows.scalars().all())

    todo = preds if force else [p for p in preds if p.top_pick_win_payoff is None]
    if not preds:
        print(f"  {target}: no settled predictions")
        return (0, 0)
    if not todo:
        print(f"  {target}: all {len(preds)} rows already priced")
        return (0, len(preds))

    try:
        data = await get_na_results_full(target.isoformat())
    except Exception as e:
        print(f"  {target}: results fetch failed ({e})")
        return (0, 0)
    by_id = {r.get("race_id"): r for r in data.get("results", []) if r.get("race_id")}

    updated = 0
    async with _db._AsyncSessionLocal() as db:
        for p in todo:
            result = by_id.get(p.race_id)
            if not result:
                continue
            payoffs = extract_top_pick_payoffs(result, p.predicted_first)
            if payoffs is None:
                continue  # unpriced chart — leave NULL, never guess
            if not dry_run:
                obj = await db.get(RacePrediction, p.id)
                obj.top_pick_win_payoff = payoffs["win"]
                obj.top_pick_place_payoff = payoffs["place"]
                obj.top_pick_show_payoff = payoffs["show"]
            updated += 1
        if not dry_run:
            await db.commit()

    # Refresh the day's report P&L columns from the freshly-priced rows.
    if not dry_run and updated:
        from app.models.accuracy import DailyAccuracyReport
        async with _db._AsyncSessionLocal() as db:
            fresh = await db.execute(
                select(RacePrediction).where(
                    RacePrediction.race_date == target,
                    RacePrediction.result_fetched == True,  # noqa: E712
                    RacePrediction.analysis_mode == "auto_daily",
                    RacePrediction.user_id.is_(None),
                )
            )
            pnl = compute_flat_bet_pnl(list(fresh.scalars().all()))
            report = await db.execute(
                select(DailyAccuracyReport).where(DailyAccuracyReport.report_date == target)
            )
            rep = report.scalar_one_or_none()
            if rep:
                rep.bet_races = pnl["races"]
                rep.bet_win_staked = pnl["win"]["staked"]
                rep.bet_win_returned = pnl["win"]["returned"]
                rep.bet_atb_staked = pnl["across_the_board"]["staked"]
                rep.bet_atb_returned = pnl["across_the_board"]["returned"]
                await db.commit()
            print(
                f"  {target}: priced {updated} rows | WIN {pnl['win']['net']:+.2f} "
                f"({pnl['win']['roi']:+.1%}) | ATB {pnl['across_the_board']['net']:+.2f} "
                f"({pnl['across_the_board']['roi']:+.1%})"
            )
    else:
        print(f"  {target}: {updated} rows would be priced [dry-run]" if dry_run
              else f"  {target}: no rows priced")
    return (updated, len(preds))


async def main(dates: list[datetime.date], dry_run: bool, force: bool):
    from app.core import database as _db
    await _db.init_db()

    # Columns may not exist yet if nightly_accuracy hasn't run since deploy.
    from sqlalchemy import text as _text
    async with _db._engine.begin() as conn:
        for col in ("top_pick_win_payoff", "top_pick_place_payoff", "top_pick_show_payoff"):
            await conn.execute(_text(f"ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS {col} FLOAT"))
        for col, typ in (("bet_races", "INTEGER DEFAULT 0"), ("bet_win_staked", "FLOAT DEFAULT 0.0"),
                         ("bet_win_returned", "FLOAT DEFAULT 0.0"), ("bet_atb_staked", "FLOAT DEFAULT 0.0"),
                         ("bet_atb_returned", "FLOAT DEFAULT 0.0")):
            await conn.execute(_text(f"ALTER TABLE daily_accuracy_reports ADD COLUMN IF NOT EXISTS {col} {typ}"))

    print(f"[backfill_payoffs] {len(dates)} date(s), dry_run={dry_run}, force={force}")
    total_updated = 0
    for d in dates:
        u, _ = await backfill_date(d, dry_run, force)
        total_updated += u
    print(f"\n✅ Priced {total_updated} races.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill official payoffs for settled races")
    ap.add_argument("--date", type=str, default=None)
    ap.add_argument("--days", type=int, default=7, help="how many days back from yesterday")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-read rows that already have payoffs")
    args = ap.parse_args()

    if args.date:
        targets = [datetime.date.fromisoformat(args.date)]
    else:
        today = datetime.date.today()
        targets = [today - datetime.timedelta(days=i) for i in range(0, args.days + 1)]
    asyncio.run(main(sorted(targets), dry_run=args.dry_run, force=args.force))
