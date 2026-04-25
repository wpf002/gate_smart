#!/usr/bin/env python3
"""
analyze_accuracy.py — Ranks Secretariat's accuracy by track, race_type,
surface, region, and (track, type)/(track, surface) combinations, relative
to the rolling baseline. Surfaces where picks are sharpest and where they
bleed.

Usage:
    cd backend
    python scripts/analyze_accuracy.py
    python scripts/analyze_accuracy.py --days 30 --min-n 10
"""
import argparse
import asyncio
import datetime
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def _rate(w: int, n: int) -> float:
    return w / n if n else 0.0


async def main(days: int, min_n: int) -> None:
    from sqlalchemy import select, and_, or_
    from app.core import database as _db
    from app.models.accuracy import RacePrediction

    await _db.init_db()
    if not _db._AsyncSessionLocal:
        print("ERROR: database not initialized")
        return

    end = datetime.date.today()
    start = end - datetime.timedelta(days=days - 1)

    async with _db._AsyncSessionLocal() as db:
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

    if not rows:
        print("No settled predictions in window.")
        return

    total_n = len(rows)
    total_w = sum(1 for r in rows if r.top_pick_correct)
    total_itm = sum(1 for r in rows if r.in_the_money)
    baseline_wr = _rate(total_w, total_n)
    baseline_itm = _rate(total_itm, total_n)

    print(f"\nAccuracy ranking — last {days}d ({start} → {end})")
    print(f"Baseline: {total_w}/{total_n} = {baseline_wr:.1%} win, {baseline_itm:.1%} ITM")
    print(f"Min sample per bucket: {min_n}\n")

    dims: dict[str, dict] = {
        "track":        defaultdict(lambda: {"n": 0, "w": 0, "itm": 0}),
        "race_type":    defaultdict(lambda: {"n": 0, "w": 0, "itm": 0}),
        "surface":      defaultdict(lambda: {"n": 0, "w": 0, "itm": 0}),
        "track+type":   defaultdict(lambda: {"n": 0, "w": 0, "itm": 0}),
        "track+surf":   defaultdict(lambda: {"n": 0, "w": 0, "itm": 0}),
    }

    for r in rows:
        t = r.track_code or "?"
        rt = r.race_type or "?"
        s = r.surface or "?"
        hit = 1 if r.top_pick_correct else 0
        itm = 1 if r.in_the_money else 0
        for key, bucket in [
            (t, dims["track"]),
            (rt, dims["race_type"]),
            (s, dims["surface"]),
            (f"{t} / {rt}", dims["track+type"]),
            (f"{t} / {s}", dims["track+surf"]),
        ]:
            bucket[key]["n"] += 1
            bucket[key]["w"] += hit
            bucket[key]["itm"] += itm

    def _print_dim(name: str, bucket: dict, min_sample: int, top_k: int = 10) -> None:
        scored = [
            (k, v["n"], v["w"], v["itm"], _rate(v["w"], v["n"]), _rate(v["itm"], v["n"]))
            for k, v in bucket.items() if v["n"] >= min_sample and "?" not in k
        ]
        if not scored:
            print(f"── {name} — no buckets meet n>={min_sample}\n")
            return
        scored.sort(key=lambda x: -x[4])
        print(f"── {name} — top {min(top_k, len(scored))} by win rate (Δ vs baseline {baseline_wr:.1%})")
        print(f"   {'Bucket':<32} {'N':>4} {'W':>3} {'Win%':>7} {'Δ':>7} {'ITM%':>7}")
        for k, n, w, itm, wr, im in scored[:top_k]:
            delta = wr - baseline_wr
            print(f"   {k:<32} {n:>4} {w:>3} {wr:>6.1%} {delta:>+7.1%} {im:>6.1%}")
        if len(scored) > top_k:
            print(f"   ── bottom {min(top_k, len(scored)-top_k)} ──")
            for k, n, w, itm, wr, im in scored[-top_k:]:
                delta = wr - baseline_wr
                print(f"   {k:<32} {n:>4} {w:>3} {wr:>6.1%} {delta:>+7.1%} {im:>6.1%}")
        print()

    _print_dim("TRACK",            dims["track"],      min_n,        top_k=10)
    _print_dim("RACE TYPE",        dims["race_type"],  min_n,        top_k=10)
    _print_dim("SURFACE",          dims["surface"],    min_n,        top_k=10)
    _print_dim("TRACK + TYPE",     dims["track+type"], max(min_n // 2, 5), top_k=10)
    _print_dim("TRACK + SURFACE",  dims["track+surf"], max(min_n // 2, 5), top_k=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30, help="Lookback window (default 30)")
    parser.add_argument("--min-n", type=int, default=10, help="Min sample per bucket (default 10)")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.min_n))
