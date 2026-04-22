#!/usr/bin/env python3
"""
nightly_predict_all.py — Morning lightweight predictions for all US races.
Uses claude-haiku at temperature=0.1 to store cheap pre-race top-4 calls.
Runs at 8 AM ET.  Cost estimate: ~$0.15/day for ~149 races.

Usage:
    cd backend
    python scripts/nightly_predict_all.py
    python scripts/nightly_predict_all.py --date 2026-04-11
    python scripts/nightly_predict_all.py --dry-run
"""
import argparse
import asyncio
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def predict_race(client, race: dict, mode: str = "auto_daily") -> dict | None:
    """Run a cheap haiku prediction on one race. Returns predicted_finish dict or None."""
    runners = race.get("runners", [])
    if not runners:
        return None

    slim = [
        {
            "num": r.get("number") or r.get("cloth_number") or "?",
            "name": r.get("horse") or r.get("horse_name", ""),
            "odds": r.get("odds", "SP"),
            "trainer": (r.get("trainer") or "")[:30],
        }
        for r in runners
    ]

    prompt = (
        f"Runners: {json.dumps(slim)}\n"
        "Return ONLY this JSON, no explanation:\n"
        '{"first": "horse_name", "second": "horse_name", '
        '"third": "horse_name", "fourth": "horse_name"}'
    )

    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # Strip fences
        if text.startswith("```"):
            text = text[text.find("\n") + 1:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"    haiku error: {e}")
    return None


async def main(target_date: datetime.date, dry_run: bool):
    import httpx
    import anthropic
    import ssl
    from app.core.config import settings
    from app.core import database as _db
    from app.models.accuracy import RacePrediction
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    await _db.init_db()

    # Ensure new columns exist (added after initial table creation)
    from sqlalchemy import text as _text
    async with _db._engine.begin() as _conn:
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS region VARCHAR(10)"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS alert_sent BOOLEAN DEFAULT FALSE"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS post_time_et VARCHAR(10)"))

    ssl_ctx = ssl.create_default_context()
    client = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        http_client=httpx.AsyncClient(verify=ssl_ctx),
    )

    from app.services.racing_api import get_na_racecards_full

    today = datetime.date.today()
    day_param = "today" if target_date == today else "tomorrow" if target_date == today + datetime.timedelta(days=1) else target_date.isoformat()

    # Fetch NA races (USA/CAN)
    print(f"\n[nightly_predict_all] Fetching NA racecards for {target_date}…")
    try:
        na_data = await get_na_racecards_full(day_param)
        na_races = [(r, "na") for r in na_data.get("racecards", [])]
    except Exception as e:
        print(f"  NA fetch failed: {e}")
        na_races = []

    all_races = na_races
    print(f"  Found {len(na_races)} NA races.")

    if not all_races:
        print("No races found — exiting.")
        return

    predicted = 0
    skipped = 0
    start_time = time.time()

    for i, (race, region) in enumerate(all_races):
        race_id = race.get("race_id") or race.get("id", "")
        race_name = race.get("race_name") or race.get("title", "")
        track_code = (race.get("course_id") or race.get("course", "") or race.get("track_code", ""))[:10]
        race_type = race.get("race_type") or race.get("type", "")
        surface = race.get("surface", "")

        if not race_id or not race.get("runners"):
            skipped += 1
            continue

        print(f"  [{i+1}/{len(all_races)}] [{region.upper()}] {race_name or race_id}", end=" … ")

        pf = await predict_race(client, race)
        if not pf:
            print("skip (no prediction)")
            skipped += 1
        else:
            first = pf.get("first", "")
            print(f"pick={first}")

            if not dry_run:
                # Extract HH:MM post time from off_dt (ISO) or time string
                post_time_et = None
                off_dt = race.get("off_dt") or race.get("off_time")
                if off_dt:
                    try:
                        import re as _re
                        m = _re.search(r'T(\d{2}:\d{2})', str(off_dt))
                        if m:
                            # Convert UTC hour to ET (subtract 4 for EDT)
                            h, mn = map(int, m.group(1).split(":"))
                            h_et = (h - 4) % 24
                            post_time_et = f"{h_et:02d}:{mn:02d}"
                    except Exception:
                        pass
                if not post_time_et:
                    raw_time = race.get("time") or race.get("post_time") or ""
                    if raw_time:
                        post_time_et = str(raw_time)[:5]

                row = {
                    "race_id": race_id,
                    "race_date": target_date,
                    "track_code": track_code,
                    "race_name": race_name,
                    "race_type": race_type,
                    "surface": surface,
                    "region": region,
                    "analysis_mode": "auto_daily",
                    "predicted_first": first,
                    "predicted_second": pf.get("second"),
                    "predicted_third": pf.get("third"),
                    "predicted_fourth": pf.get("fourth"),
                    "post_time_et": post_time_et,
                }
                from sqlalchemy import update as _update, or_ as _or_
                async with _db._AsyncSessionLocal() as db:
                    stmt = pg_insert(RacePrediction).values(**row)
                    stmt = stmt.on_conflict_do_nothing(constraint="uq_race_prediction")
                    await db.execute(stmt)
                    # Backfill race_type on rows that already exist with an empty value.
                    # ON CONFLICT DO NOTHING skips new inserts, so this ensures existing
                    # rows are patched if the API now returns a type it didn't before.
                    if race_type:
                        await db.execute(
                            _update(RacePrediction)
                            .where(
                                RacePrediction.race_id == race_id,
                                RacePrediction.analysis_mode == "auto_daily",
                                _or_(
                                    RacePrediction.race_type.is_(None),
                                    RacePrediction.race_type == "",
                                ),
                            )
                            .values(race_type=race_type)
                        )
                    await db.commit()

            predicted += 1

        await asyncio.sleep(1.0)

    elapsed = time.time() - start_time
    cost_est = predicted * 0.001
    print(f"\n✅ Done: {predicted} predicted ({len(na_races)} NA), {skipped} skipped in {elapsed:.0f}s")
    print(f"   Estimated cost: ~${cost_est:.3f}")
    if dry_run:
        print("   [DRY RUN] No rows written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Morning predict-all races")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    asyncio.run(main(target_date=target, dry_run=args.dry_run))
