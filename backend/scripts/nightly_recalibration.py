#!/usr/bin/env python3
"""
nightly_recalibration.py — Reads 30-day rolling predictions and updates
SecretariatCalibration so tomorrow's analysis prompts include self-awareness.

Usage:
    cd backend
    python scripts/nightly_recalibration.py
    python scripts/nightly_recalibration.py --dry-run
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


async def _ensure_columns(engine) -> None:
    """Add columns that were introduced after initial table creation."""
    ddl = [
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS reflection TEXT",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS region VARCHAR(10)",
        "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS lessons JSONB",
    ]
    async with engine.begin() as conn:
        for stmt in ddl:
            await conn.execute(__import__("sqlalchemy").text(stmt))


def _win_rate(wins: int, total: int) -> float:
    return wins / total if total else 0.0


def _categorise(data: dict, min_samples: int = 10, low: float = 0.35, high: float = 0.55):
    """Split a {category: {wins, total}} dict into weak/strong spots."""
    weak, strong = [], []
    for cat, counts in data.items():
        total = counts["total"]
        if total < min_samples:
            continue
        wr = _win_rate(counts["wins"], total)
        label = f"{cat} ({wr:.0%} win rate, {total} races)"
        if wr < low:
            weak.append(label)
        elif wr > high:
            strong.append(label)
    return weak, strong


async def main(dry_run: bool):
    from app.core import database as _db
    from app.models.accuracy import RacePrediction, SecretariatCalibration
    from sqlalchemy import select

    await _db.init_db()
    await _ensure_columns(_db._engine)

    cutoff = datetime.date.today() - datetime.timedelta(days=30)

    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date >= cutoff,
                RacePrediction.result_fetched == True,  # noqa: E712
                # NA-only calibration — international racing has different patterns
                (RacePrediction.region == "na") | (RacePrediction.region == None),  # noqa: E711
            )
        )
        predictions = result.scalars().all()

    total = len(predictions)
    wins = sum(1 for p in predictions if p.top_pick_correct)
    rolling_win_rate = _win_rate(wins, total)

    print(f"\n[nightly_recalibration] 30-day window: {total} races, {wins} wins ({rolling_win_rate:.1%})")

    # By analysis_mode
    by_mode: dict = defaultdict(lambda: {"wins": 0, "total": 0})
    by_track: dict = defaultdict(lambda: {"wins": 0, "total": 0})
    by_type: dict = defaultdict(lambda: {"wins": 0, "total": 0})
    by_surface: dict = defaultdict(lambda: {"wins": 0, "total": 0})

    for p in predictions:
        for bucket, key in [
            (by_mode, p.analysis_mode or "unknown"),
            (by_track, p.track_code or "unknown"),
            (by_type, p.race_type or "unknown"),
            (by_surface, p.surface or "unknown"),
        ]:
            bucket[key]["total"] += 1
            if p.top_pick_correct:
                bucket[key]["wins"] += 1

    # Convert to plain dicts with win_rate for storage
    def _to_rates(bucket):
        return {
            k: {"wins": v["wins"], "total": v["total"], "win_rate": round(_win_rate(v["wins"], v["total"]), 3)}
            for k, v in bucket.items()
        }

    mode_rates = _to_rates(by_mode)
    track_rates = _to_rates(by_track)
    type_rates = _to_rates(by_type)
    surface_rates = _to_rates(by_surface)

    weak_track, strong_track = _categorise(by_track)
    weak_type, strong_type = _categorise(by_type)
    weak_surface, strong_surface = _categorise(by_surface)

    weak_spots = weak_track + weak_type + weak_surface
    strong_spots = strong_track + strong_type + strong_surface

    print(f"  Weak spots ({len(weak_spots)}): {weak_spots}")
    print(f"  Strong spots ({len(strong_spots)}): {strong_spots}")
    print("  By mode:", {k: f"{v['wins']}/{v['total']} ({v['win_rate']:.0%})" for k, v in mode_rates.items()})

    if dry_run:
        print("\n[DRY RUN] Not writing to DB.")
        return

    async with _db._AsyncSessionLocal() as db:
        existing = await db.get(SecretariatCalibration, 1)
        now = datetime.datetime.now(datetime.timezone.utc)

        if existing:
            existing.updated_at = now
            existing.rolling_win_rate = rolling_win_rate
            existing.win_rate_by_mode = mode_rates
            existing.win_rate_by_track = track_rates
            existing.win_rate_by_type = type_rates
            existing.win_rate_by_surface = surface_rates
            existing.weak_spots = weak_spots[:10]
            existing.strong_spots = strong_spots[:10]
            existing.sample_size = total
        else:
            db.add(SecretariatCalibration(
                id=1,
                updated_at=now,
                rolling_win_rate=rolling_win_rate,
                win_rate_by_mode=mode_rates,
                win_rate_by_track=track_rates,
                win_rate_by_type=type_rates,
                win_rate_by_surface=surface_rates,
                weak_spots=weak_spots[:10],
                strong_spots=strong_spots[:10],
                sample_size=total,
            ))
        await db.commit()

    print("\n✅ SecretariatCalibration updated (id=1).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly recalibration")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
