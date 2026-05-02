#!/usr/bin/env python3
"""
morning_line_email.py — Sends Secretariat's pre-race "Morning Line" email.

Runs after nightly_predict_all.py has populated today's RacePrediction rows.
Pulls today's NA picks (no LLM call), composes a W/P/S email per race grouped
by track, and sends via Resend.

Usage:
    cd backend
    python scripts/morning_line_email.py
    python scripts/morning_line_email.py --date 2026-05-02
    python scripts/morning_line_email.py --dry-run
"""
import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def _ensure_columns(engine) -> None:
    """Backfill columns added after initial table creation (mirrors nightly_accuracy.py)."""
    from sqlalchemy import text
    ddl = [
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS reflection TEXT",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS region VARCHAR(10)",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS place_pick_correct BOOLEAN",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS show_pick_correct BOOLEAN",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS alert_sent BOOLEAN DEFAULT FALSE",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS post_time_et VARCHAR(10)",
        "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS lessons JSONB",
    ]
    async with engine.begin() as conn:
        for stmt in ddl:
            await conn.execute(text(stmt))


async def main(target_date: datetime.date, dry_run: bool):
    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from app.services.secretariat import generate_morning_line_email
    from app.services.email_service import send_daily_report
    from sqlalchemy import select, or_

    await _db.init_db()
    await _ensure_columns(_db._engine)

    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date == target_date,
                or_(RacePrediction.region == "na", RacePrediction.region == None),  # noqa: E711
                RacePrediction.user_id == None,  # noqa: E711  global auto-prediction rows
            )
        )
        predictions = list(result.scalars().all())

    print(f"\n[morning_line_email] Date: {target_date} | Picks: {len(predictions)} | dry_run={dry_run}")

    if not predictions:
        print("No predictions for today — exiting (did nightly_predict_all run?).")
        return

    email = await generate_morning_line_email(predictions, target_date)

    if dry_run:
        print(f"\nSubject: {email['subject']}\n")
        print(email["text"][:2000])
        return

    sent = await send_daily_report(
        subject=email["subject"],
        html_body=email["html"],
        text_body=email["text"],
    )
    print(f"  send_daily_report → {sent}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (defaults to today)")
    parser.add_argument("--dry-run", action="store_true", help="Print email instead of sending")
    args = parser.parse_args()

    target = (
        datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    )
    asyncio.run(main(target, args.dry_run))
