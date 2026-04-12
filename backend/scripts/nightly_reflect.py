#!/usr/bin/env python3
"""
nightly_reflect.py — Post-race reflection layer.

After results are settled (by nightly_accuracy.py), Secretariat reviews every
race it predicted: why did the correct picks work, and what went wrong on misses?
Lessons are synthesised and stored in SecretariatCalibration.lessons, which are
injected into every future analysis prompt so Secretariat genuinely improves
over time.

Pipeline order (nightly):
  11 PM ET  — nightly_accuracy.py   (settle results)
  11:30 PM  — nightly_recalibration.py (recalibrate weights)
  Midnight  — nightly_reflect.py    (this script — reflect & synthesise)

Usage:
    cd backend
    python scripts/nightly_reflect.py
    python scripts/nightly_reflect.py --date 2026-04-11
    python scripts/nightly_reflect.py --dry-run
"""
import argparse
import asyncio
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Races per batch for per-race reflection calls (keeps cost low)
BATCH_SIZE = 10


async def _ensure_columns(engine) -> None:
    """Add new columns to existing tables if they don't exist yet."""
    ddl = [
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS reflection TEXT",
        "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS lessons JSONB",
    ]
    async with engine.begin() as conn:
        for stmt in ddl:
            await conn.execute(__import__("sqlalchemy").text(stmt))


async def reflect_batch(client, races: list[dict]) -> list[dict]:
    """
    Ask Secretariat to reflect on a batch of races (mix of hits and misses).
    Returns a list of {race_id, factor, lesson} dicts.
    """
    items = []
    for r in races:
        outcome = "CORRECT" if r["hit"] else "MISSED"
        items.append(
            f"- [{outcome}] {r['race_name']} | track={r['track']} surface={r['surface']} "
            f"type={r['race_type']} | picked={r['predicted']} actual={r['actual']}"
        )

    prompt = (
        "You are Secretariat reviewing yesterday's predictions. "
        "For each race below, return a JSON array. Each element must have:\n"
        '  "race_id": the race_id string\n'
        '  "factor": the single most important factor that explains the outcome '
        "(e.g. pace collapse, surface switch, class drop, connections, market drift, trainer pattern)\n"
        '  "lesson": one concise sentence — what to weigh differently next time in similar races\n\n'
        "Races:\n"
        + "\n".join(f"  race_id={r['race_id']} {line}" for r, line in zip(races, items))
        + "\n\nReturn ONLY valid JSON array, no explanation."
    )

    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text[text.find("\n") + 1:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        start, end = text.find("["), text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"    reflect_batch error: {e}")
    return []


async def synthesise_lessons(client, reflections: list[dict], date_str: str) -> list[str]:
    """
    One Sonnet call to synthesise 5 durable lessons from all of yesterday's reflections.
    Returns a list of lesson strings suitable for injection into future prompts.
    """
    hits = [r for r in reflections if r.get("hit")]
    misses = [r for r in reflections if not r.get("hit")]

    summary_lines = []
    if misses:
        summary_lines.append(f"MISSES ({len(misses)}):")
        for r in misses[:30]:  # cap to avoid blowing context
            summary_lines.append(
                f"  - {r['race_name']} | picked {r['predicted']}, actual {r['actual']} "
                f"| surface={r['surface']} type={r['race_type']} | factor={r.get('factor','')} | {r.get('lesson','')}"
            )
    if hits:
        summary_lines.append(f"CORRECT PICKS ({len(hits)}):")
        for r in hits[:20]:
            summary_lines.append(
                f"  - {r['race_name']} | {r['predicted']} won "
                f"| surface={r['surface']} type={r['race_type']} | factor={r.get('factor','')} | {r.get('lesson','')}"
            )

    prompt = (
        f"You are Secretariat reviewing your performance on {date_str}.\n\n"
        + "\n".join(summary_lines)
        + "\n\nBased on this, write exactly 5 durable lessons I should carry into every future race "
        "I handicap. Each lesson must be:\n"
        "- Specific and actionable (not generic like 'consider all factors')\n"
        "- Applicable across multiple races, not a one-off observation\n"
        "- Written in first person (e.g. 'When the surface switches to turf, I tend to over-rely on dirt speed figures...')\n\n"
        'Return ONLY a JSON array of 5 strings. Example: ["lesson 1", "lesson 2", ...]'
    )

    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text[text.find("\n") + 1:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        start, end = text.find("["), text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"    synthesise_lessons error: {e}")
    return []


async def main(target_date: datetime.date, dry_run: bool):
    import httpx
    import anthropic
    import ssl
    from app.core.config import settings
    from app.core import database as _db
    from app.models.accuracy import RacePrediction, SecretariatCalibration
    from sqlalchemy import select, update

    await _db.init_db()
    await _ensure_columns(_db._engine)

    ssl_ctx = ssl.create_default_context()
    client = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        http_client=httpx.AsyncClient(verify=ssl_ctx),
    )

    print(f"\n[nightly_reflect] Reflecting on {target_date} | dry_run={dry_run}")

    # 1. Load all settled predictions for target_date
    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date == target_date,
                RacePrediction.result_fetched == True,  # noqa: E712
            )
        )
        predictions = result.scalars().all()

    if not predictions:
        print("No settled predictions to reflect on — exiting.")
        return

    total = len(predictions)
    hits = sum(1 for p in predictions if p.top_pick_correct)
    misses = total - hits
    print(f"  {total} settled predictions: {hits} correct, {misses} missed")

    # 2. Build race dicts for reflection
    race_dicts = [
        {
            "race_id": p.race_id,
            "race_name": p.race_name or p.race_id,
            "track": p.track_code or "?",
            "surface": p.surface or "?",
            "race_type": p.race_type or "?",
            "predicted": p.predicted_first or "?",
            "actual": p.actual_first or "?",
            "hit": bool(p.top_pick_correct),
            "db_id": p.id,
        }
        for p in predictions
    ]

    # 3. Batch reflection calls (Haiku — cheap)
    all_reflections: list[dict] = []
    for i in range(0, len(race_dicts), BATCH_SIZE):
        batch = race_dicts[i: i + BATCH_SIZE]
        print(f"  Reflecting batch {i // BATCH_SIZE + 1}/{(len(race_dicts) + BATCH_SIZE - 1) // BATCH_SIZE}…")
        results = await reflect_batch(client, batch)

        # Merge factor/lesson back into race_dicts
        keyed = {r.get("race_id"): r for r in results}
        for rd in batch:
            if rd["race_id"] in keyed:
                rd["factor"] = keyed[rd["race_id"]].get("factor", "")
                rd["lesson"] = keyed[rd["race_id"]].get("lesson", "")
            else:
                rd["factor"] = ""
                rd["lesson"] = ""
        all_reflections.extend(batch)
        await asyncio.sleep(0.5)  # gentle rate limit

    # 4. Write per-race reflections to DB
    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            for rd in all_reflections:
                reflection_text = (
                    f"Factor: {rd['factor']}. {rd['lesson']}" if rd.get("factor") else rd.get("lesson", "")
                )
                if reflection_text:
                    await db.execute(
                        update(RacePrediction)
                        .where(RacePrediction.id == rd["db_id"])
                        .values(reflection=reflection_text)
                    )
            await db.commit()
        print(f"  ✅ Wrote reflections for {len(all_reflections)} races.")

    # 5. Synthesise 5 durable lessons (Sonnet — one call)
    print("  Synthesising lessons…")
    date_str = target_date.strftime("%B %d, %Y")
    lessons = await synthesise_lessons(client, all_reflections, date_str)

    if not lessons:
        print("  ⚠️  No lessons synthesised — skipping calibration update.")
        return

    print(f"\n  📚 {len(lessons)} lessons for future predictions:")
    for i, lesson in enumerate(lessons, 1):
        print(f"    {i}. {lesson}")

    # 6. Append to SecretariatCalibration.lessons (keep last 30 — rolling window)
    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            cal = await db.get(SecretariatCalibration, 1)
            if cal:
                existing = cal.lessons or []
                # Prepend today's lessons, keep at most 30 total
                updated = lessons + [l for l in existing if l not in lessons]
                updated = updated[:30]
                cal.lessons = updated
                cal.updated_at = datetime.datetime.now(datetime.timezone.utc)
            else:
                # No calibration row yet — create one with just lessons
                from app.models.accuracy import SecretariatCalibration as _Cal
                db.add(_Cal(
                    id=1,
                    updated_at=datetime.datetime.now(datetime.timezone.utc),
                    rolling_win_rate=0.0,
                    sample_size=0,
                    lessons=lessons,
                ))
            await db.commit()
        print(f"\n✅ SecretariatCalibration.lessons updated ({len(lessons)} new).")

    if dry_run:
        print("\n[DRY RUN] No rows written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nightly post-race reflection")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (defaults to yesterday)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Default to yesterday — accuracy runs at 11 PM on race day, reflect at midnight
    if args.date:
        target = datetime.date.fromisoformat(args.date)
    else:
        target = datetime.date.today() - datetime.timedelta(days=1)

    asyncio.run(main(target_date=target, dry_run=args.dry_run))
