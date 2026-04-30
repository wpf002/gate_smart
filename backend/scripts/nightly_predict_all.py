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


def _format_bucket_hint(track: str, race_type: str, surface: str, cal) -> str | None:
    """Build a short calibration block giving the model its own historical
    top-pick win rate in this bucket. Stats only — no directive language —
    so the model's pick stays authentic to its own analysis, with metacognition
    rather than steering. Returns None if no usable calibration data.

    Most-specific data wins: (track, race_type) combo > track-only > type-only.
    A bucket needs at least 5 prior samples to be cited.
    """
    if not cal:
        return None
    baseline = cal.rolling_win_rate or 0.0
    if not baseline:
        return None

    by_tt = cal.win_rate_by_track_type or {}
    by_t = cal.win_rate_by_track or {}
    by_rt = cal.win_rate_by_type or {}

    parts = [f"Your top-pick win rate over the last 30 days: {baseline:.0%}."]

    combo = by_tt.get(f"{track}/{race_type}")
    if combo and combo.get("total", 0) >= 5:
        wr = combo["win_rate"]
        parts.append(f"At {track} / {race_type}: {combo['wins']}/{combo['total']} ({wr:.0%}).")
    else:
        # Fall back to broader signals when combo sample is too thin
        t_data = by_t.get(track)
        if t_data and t_data.get("total", 0) >= 8:
            wr = t_data["win_rate"]
            parts.append(f"At {track} overall: {t_data['wins']}/{t_data['total']} ({wr:.0%}).")
        rt_data = by_rt.get(race_type)
        if rt_data and rt_data.get("total", 0) >= 8:
            wr = rt_data["win_rate"]
            parts.append(f"On {race_type}: {rt_data['wins']}/{rt_data['total']} ({wr:.0%}).")

    return " ".join(parts) if len(parts) > 1 else None


async def predict_race(
    client,
    race: dict,
    mode: str = "auto_daily",
    bucket_hint: str | None = None,
) -> dict | None:
    """Run a cheap haiku prediction on one race. Returns predicted_finish dict or None.

    `bucket_hint`, when supplied, is a one-line calibration string injected at
    the top of the prompt so haiku can adjust confidence based on Secretariat's
    own historical accuracy in this track/type combination.
    """
    runners = race.get("runners", [])
    if not runners:
        return None

    # Filter scratches — picking a horse that won't run is a guaranteed miss
    # and a stale alert. Field size below 2 isn't a race to handicap.
    active = [r for r in runners if not (r.get("scratched") or r.get("non_runner"))]
    if len(active) < 2:
        return None

    slim = []
    for r in active:
        entry = {
            "pp": str(r.get("number") or r.get("program_number") or r.get("cloth_number") or "?"),
            "name": r.get("horse") or r.get("horse_name", ""),
            "odds": r.get("odds") or r.get("sp") or "SP",
            "jockey": (r.get("jockey") or "")[:30],
            "trainer": (r.get("trainer") or "")[:30],
        }
        # Optional fields only when present — keeps the prompt compact
        if r.get("weight"):
            entry["weight"] = r.get("weight")
        if r.get("claiming_price"):
            entry["claim"] = r.get("claiming_price")
        if r.get("age"):
            entry["age"] = r.get("age")
        if r.get("sex"):
            entry["sex"] = r.get("sex")
        slim.append(entry)

    # Race-level context — the same horse needs different handicapping at 5f vs 1m,
    # on a fast dirt track vs muddy turf, in a maiden vs a graded stakes.
    distance = race.get("distance") or (f"{race.get('distance_f')}f" if race.get("distance_f") else "")
    race_ctx = {
        k: v for k, v in {
            "distance": distance,
            "surface": race.get("surface", ""),
            "going": race.get("going", ""),  # track condition
            "race_class": race.get("race_class", ""),
            "race_type": race.get("race_type", ""),
            "purse": race.get("prize"),
            "field_size": len(active),
        }.items() if v
    }

    prompt = (
        (bucket_hint + "\n\n" if bucket_hint else "")
        + f"Race: {json.dumps(race_ctx)}\n"
        f"Runners (scratched horses already removed): {json.dumps(slim)}\n\n"
        "Pick the four most likely finishers. Use ONLY names from the runner list above.\n"
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

    # Load Secretariat's own calibration once — feeds bucket-specific accuracy
    # context into every haiku prompt below so picks adjust to historical performance.
    from app.models.accuracy import SecretariatCalibration
    async with _db._AsyncSessionLocal() as _cal_db:
        calibration = await _cal_db.get(SecretariatCalibration, 1)
    if calibration and calibration.sample_size:
        print(f"  Loaded calibration: {calibration.sample_size} races, {calibration.rolling_win_rate:.0%} win rate baseline")
    else:
        print("  No calibration data yet — running without bucket hints")
        calibration = None

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

        bucket_hint = _format_bucket_hint(track_code, race_type, surface, calibration)
        pf = await predict_race(client, race, bucket_hint=bucket_hint)
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
