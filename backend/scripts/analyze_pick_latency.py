#!/usr/bin/env python3
"""
analyze_pick_latency.py — Bins settled NA predictions by pick→post latency
and reports win rate per bin, so you can see whether stale picks (made hours
before post) underperform fresh ones (made shortly before post).

Usage:
    cd backend
    python scripts/analyze_pick_latency.py
    python scripts/analyze_pick_latency.py --days 30
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def _post_dt_for(race_date: datetime.date, post_time_et: str) -> datetime.datetime | None:
    if not post_time_et or len(post_time_et) < 4:
        return None
    try:
        h, m = map(int, post_time_et.split(":")[:2])
    except ValueError:
        return None
    # post_time_et is naive ET; treat as UTC-4 (EDT) to compare against UTC created_at
    return datetime.datetime(
        race_date.year, race_date.month, race_date.day, h, m,
        tzinfo=datetime.timezone(datetime.timedelta(hours=-4)),
    )


def _bin_for(hours: float) -> str:
    if hours < 1:
        return "<1h"
    if hours < 3:
        return "1–3h"
    if hours < 6:
        return "3–6h"
    if hours < 10:
        return "6–10h"
    return "10h+"


_BIN_ORDER = ["<1h", "1–3h", "3–6h", "6–10h", "10h+"]


async def main(days: int) -> None:
    from sqlalchemy import select, and_, or_
    from app.core.database import _AsyncSessionLocal, init_db
    from app.models.accuracy import RacePrediction

    await init_db()
    if not _AsyncSessionLocal:
        print("ERROR: database not initialized")
        return

    end = datetime.date.today()
    start = end - datetime.timedelta(days=days - 1)

    async with _AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                and_(
                    RacePrediction.race_date >= start,
                    RacePrediction.race_date <= end,
                    RacePrediction.result_fetched == True,  # noqa: E712
                    or_(RacePrediction.region == "na", RacePrediction.region == None),  # noqa: E711
                )
            )
        )
        rows = result.scalars().all()

    print(f"\nPick→post latency analysis  ({start} → {end}, {len(rows)} settled NA picks)\n")

    bins: dict[str, dict] = {b: {"n": 0, "w": 0, "itm": 0} for b in _BIN_ORDER}
    skipped = 0

    for r in rows:
        post_dt = _post_dt_for(r.race_date, r.post_time_et or "")
        if not post_dt or not r.created_at:
            skipped += 1
            continue
        # created_at is timezone-aware UTC; post_dt is timezone-aware ET
        delta = (post_dt - r.created_at).total_seconds() / 3600.0
        if delta < -1 or delta > 30:
            # Pick made after post (data error) or absurdly early — skip
            skipped += 1
            continue
        b = bins[_bin_for(max(delta, 0))]
        b["n"] += 1
        if r.top_pick_correct:
            b["w"] += 1
        if r.in_the_money:
            b["itm"] += 1

    print(f"  {'Latency':<8} {'N':>5}  {'Wins':>5}  {'Win%':>6}  {'ITM%':>6}")
    print("  " + "-" * 38)
    total_n = total_w = total_itm = 0
    for b in _BIN_ORDER:
        d = bins[b]
        total_n += d["n"]
        total_w += d["w"]
        total_itm += d["itm"]
        if d["n"] == 0:
            print(f"  {b:<8} {0:>5}  {'—':>5}  {'—':>6}  {'—':>6}")
            continue
        wr = d["w"] / d["n"]
        itm = d["itm"] / d["n"]
        print(f"  {b:<8} {d['n']:>5}  {d['w']:>5}  {wr:>6.1%}  {itm:>6.1%}")

    print("  " + "-" * 38)
    if total_n:
        print(f"  {'TOTAL':<8} {total_n:>5}  {total_w:>5}  {total_w/total_n:>6.1%}  {total_itm/total_n:>6.1%}")
    print(f"\n  Skipped (missing post_time_et or out-of-range): {skipped}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14, help="Lookback window (default 14)")
    args = parser.parse_args()
    asyncio.run(main(args.days))
