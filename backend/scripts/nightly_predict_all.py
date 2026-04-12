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

    ssl_ctx = ssl.create_default_context()
    client = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        http_client=httpx.AsyncClient(verify=ssl_ctx),
    )

    # Fetch today's US racecards
    print(f"\n[nightly_predict_all] Fetching US racecards for {target_date}…")
    date_str = target_date.strftime("%Y-%m-%d")
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                "https://api.theracingapi.com/v1/racecards/pro",
                params={"date": date_str, "region": "usa"},
                auth=(settings.RACING_API_USERNAME, settings.RACING_API_PASSWORD),
            )
        if resp.status_code != 200:
            print(f"API {resp.status_code} — trying standard endpoint")
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.get(
                    "https://api.theracingapi.com/v1/racecards",
                    params={"date": date_str, "region": "usa"},
                    auth=(settings.RACING_API_USERNAME, settings.RACING_API_PASSWORD),
                )
        data = resp.json()
    except Exception as e:
        print(f"Failed to fetch racecards: {e}")
        return

    # Flatten races from response
    races = []
    if isinstance(data, list):
        races = data
    elif isinstance(data, dict):
        for key in ("racecards", "races", "results"):
            if key in data and isinstance(data[key], list):
                races = data[key]
                break

    print(f"  Found {len(races)} races.")

    if not races:
        print("No races found — exiting.")
        return

    predicted = 0
    skipped = 0
    start_time = time.time()

    for i, race in enumerate(races):
        race_id = race.get("race_id") or race.get("id", "")
        race_name = race.get("race_name") or race.get("title", "")
        track_code = (race.get("course_id") or race.get("course", ""))[:10]
        race_type = race.get("race_type") or race.get("type", "")
        surface = race.get("surface", "")

        if not race_id or not race.get("runners"):
            skipped += 1
            continue

        print(f"  [{i+1}/{len(races)}] {race_name or race_id}", end=" … ")

        pf = await predict_race(client, race)
        if not pf:
            print("skip (no prediction)")
            skipped += 1
        else:
            first = pf.get("first", "")
            print(f"pick={first}")

            if not dry_run:
                row = {
                    "race_id": race_id,
                    "race_date": target_date,
                    "track_code": track_code,
                    "race_name": race_name,
                    "race_type": race_type,
                    "surface": surface,
                    "analysis_mode": "auto_daily",
                    "predicted_first": first,
                    "predicted_second": pf.get("second"),
                    "predicted_third": pf.get("third"),
                    "predicted_fourth": pf.get("fourth"),
                }
                async with _db._AsyncSessionLocal() as db:
                    stmt = pg_insert(RacePrediction).values(**row)
                    stmt = stmt.on_conflict_do_nothing(constraint="uq_race_prediction")
                    await db.execute(stmt)
                    await db.commit()

            predicted += 1

        # Rate limit: 1 req/sec
        await asyncio.sleep(1.0)

    elapsed = time.time() - start_time
    cost_est = predicted * 0.001  # rough haiku estimate
    print(f"\n✅ Done: {predicted} predicted, {skipped} skipped in {elapsed:.0f}s")
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
