#!/usr/bin/env python3
"""
nightly_reflect.py — Post-race reflection layer.

After results are settled (by nightly_accuracy.py), Secretariat reviews every
race it predicted: why did the correct picks work, and what went wrong on misses?
Lessons are synthesised and stored in SecretariatCalibration.lessons, which are
injected into every future analysis prompt so Secretariat genuinely improves
over time.

Pipeline order (UTC) — reflect MUST run after accuracy settles, or it finds
no settled predictions and the learning loop never advances:
  10:00  nightly_accuracy.py        (settle yesterday's results)
  14:30  nightly_reflect.py         (this script — reflect & synthesise)

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

# Races per batch for per-race reflection calls. Kept small so the JSON array
# response fits comfortably under reflect_batch's max_tokens — a batch that
# overflows the cap truncates mid-array, fails to parse, and silently yields
# zero reflections (which is what broke the learning loop for weeks).
BATCH_SIZE = 12


async def _ensure_columns(engine) -> None:
    """Add new columns to existing tables if they don't exist yet."""
    ddl = [
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS reflection TEXT",
        "ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS region VARCHAR(10)",
        "ALTER TABLE secretariat_calibration ADD COLUMN IF NOT EXISTS lessons JSONB",
    ]
    async with engine.begin() as conn:
        for stmt in ddl:
            await conn.execute(__import__("sqlalchemy").text(stmt))


async def reflect_batch(client, races: list[dict]) -> list[dict]:
    """
    Reflect on a batch of races, distinguishing hits from misses.
    Returns list of {race_id, hit, factor, lesson_type, lesson} dicts.
    lesson_type is "continue" (hit) or "change" (miss).
    """
    items = []
    for r in races:
        outcome = "CORRECT" if r["hit"] else "MISSED"
        # Build my full predicted top-3 with hit/miss flags so the model can
        # compare its own ranking against the actual finishing order, not just
        # win pick vs winner.
        my_picks = [f"W:{r.get('predicted') or '?'}{'✓' if r['hit'] else '✗'}"]
        if r.get("predicted_second"):
            my_picks.append(
                f"P:{r['predicted_second']}{'✓' if r.get('place_pick_correct') else '✗'}"
            )
        if r.get("predicted_third"):
            my_picks.append(
                f"S:{r['predicted_third']}{'✓' if r.get('show_pick_correct') else '✗'}"
            )
        my_picks_str = " ".join(my_picks)

        actual_top3 = [r.get("actual") or "?"]
        if r.get("actual_second"):
            actual_top3.append(r["actual_second"])
        if r.get("actual_third"):
            actual_top3.append(r["actual_third"])
        actual_str = " | ".join(actual_top3)

        line = (
            f"  race_id={r['race_id']} [{outcome}] {r['race_name']} "
            f"track={r['track']} surface={r['surface']} type={r['race_type']}\n"
            f"      my picks (top-3): {my_picks_str}\n"
            f"      actual top-3: {actual_str}"
        )
        # Append official-results context: top-3 W/P/S payoffs and exotic
        # payoffs. Lets Secretariat reason about value (chalk vs longshot)
        # and whether his P/S picks formed hittable exactas/trifectas.
        finish_str = r.get("finish_str") or ""
        exotic_str = r.get("exotic_str") or ""
        if finish_str:
            line += f"\n      finish + payoffs: {finish_str}"
        if exotic_str:
            line += f"\n      exotics: {exotic_str}"
        items.append(line)

    prompt = (
        "You are Secretariat reviewing your predictions. For each race you see:\n"
        "  - my full predicted top-3 (W = win pick, P = place pick, S = show pick) with ✓/✗ flags "
        "showing which of my picks landed in the corresponding pool\n"
        "  - the actual top-3 finishers in finishing order\n"
        "  - the official $2 W/P/S payoffs for each finisher\n"
        "  - the exotic wager payoffs (Exacta, Trifecta, Superfecta, Daily Double, Pick 3/4/5, etc.)\n\n"
        "Compare my full top-3 to the actual top-3, not just win vs winner. The most valuable insight "
        "is often: my top pick missed but my P or S landed — was the runner I underweighted obvious in "
        "hindsight? Or: I had the right horses but wrong order — what would have flipped the ranking?\n"
        "Use the payoffs to judge value: a $4.20 win payoff is heavy chalk, a $24.00 win payoff is a live longshot. "
        "When reflecting on a CORRECT pick, note whether the win was at a price worth backing or just a chalk hit. "
        "When reflecting on a MISS, note whether the actual winner was an obvious favorite you should have caught "
        "or a price horse that was hard to see — and whether the exotic payoffs suggest a hittable combo "
        "(my P/S picks plus the actual winner) I should have surfaced.\n\n"
        "DO NOT attribute a miss to confusing, misidentifying, or mixing up horse names, even when the "
        "winner's name resembles one of your picks. You select from the exact runner list, so name "
        "confusion is never the real reason — picking the wrong horse is a handicapping judgment error, "
        "not an identity error. Reflect only on factors you can verify from the data: pace, class, form, "
        "price/value, post, pace shape, trainer/jockey, layoff.\n\n"
        "For each race return a JSON array element with:\n"
        '  "race_id": string\n'
        '  "factor": a short phrase (2-5 words) naming the single key factor that explains the outcome — '
        "use whatever wording fits the race (pace, post, class, price, exotic structure); "
        "do not constrain yourself to a fixed vocabulary\n"
        '  "lesson_type": "continue" if CORRECT (this reasoning worked, keep it), '
        '"change" if MISSED (this reasoning failed, adjust it)\n'
        '  "lesson": one sentence — for CORRECT: what signal to keep trusting (cite the price/payoff if relevant); '
        "for MISSED: what specific thing to weigh differently next time (cite the winner's price or exotic payoff "
        "if it changes the lesson)\n\n"
        "Races:\n" + "\n".join(items)
        + "\n\nReturn ONLY a valid JSON array, no explanation."
    )

    try:
        from app.core.llm_cost import tracked_create
        resp = await tracked_create(
            client,
            endpoint="nightly_reflect_batch",
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(resp, "stop_reason", None) == "max_tokens":
            print(
                f"    ⚠️  reflect_batch hit max_tokens with {len(races)} races — "
                f"JSON likely truncated. Lower BATCH_SIZE or raise max_tokens."
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


async def curate_lessons(
    client,
    candidates: list[str],
    trends_block: str,
    date_str: str,
    cap: int = 15,
) -> list[str]:
    """
    Review the merged lesson list (today's new + existing rolling) against the
    7-day trend data and drop the ones that aren't earning their place.

    Why this exists: lessons accumulate FIFO and dilute over time. A lesson that
    targeted "maiden races" 3 weeks ago may still sit in the prompt even though
    the trend data shows maiden performance has not improved (or has regressed).
    Better to actively retire those than push them out the back of a 30-slot window.

    Returns at most `cap` lessons, picked verbatim from `candidates` (no rewrites).
    """
    if not candidates:
        return []

    numbered = "\n".join(f"  {i+1}. {l}" for i, l in enumerate(candidates))
    trends_section = f"\n7-DAY TREND DATA:\n{trends_block}\n" if trends_block else ""

    prompt = (
        f"You are Secretariat curating your active playbook on {date_str}.\n\n"
        f"CANDIDATE LESSONS ({len(candidates)} total — newest first):\n{numbered}\n"
        f"{trends_section}\n"
        "Only the top few of these get injected into every future pick, so keep the ones that "
        "genuinely sharpen handicapping. Drop:\n"
        "- Lessons built on small-sample noise (a single day/card/week box score like '0/10 today', "
        "'2/9 on one card', '3/8 in a week') — those reflect luck, not a real edge\n"
        "- Hyper-specific micro-rules tied to one track + surface + race-type, when a more general "
        "principle covers the same ground (favor the transferable principle)\n"
        "- Meta-commentary or self-grading ('I'm not applying my lesson', 'still unproven') — keep "
        "only lessons that encode predictive knowledge\n"
        "- Lessons whose target category has NOT improved (or has regressed) in the trend data\n"
        "- Older lessons made redundant by newer ones, lessons that contradict newer evidence, and "
        "vague lessons when a sharper one targets the same area\n\n"
        f"Keep at most {cap}. Quality over quantity — a few durable, general principles beat a long "
        "list of narrow or noisy ones. Do NOT rewrite lessons; return them verbatim from the candidate list above.\n\n"
        "Return ONLY a JSON array of strings (the kept lessons, in priority order)."
    )

    try:
        from app.core.llm_cost import tracked_create
        resp = await tracked_create(
            client,
            endpoint="nightly_reflect_curate",
            model="claude-sonnet-4-6",
            max_tokens=2000,
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
            kept = json.loads(text[start:end])
            cand_set = set(candidates)
            # Belt-and-suspenders: only keep strings that were in the candidates,
            # so the model can't sneak in a paraphrased / hallucinated lesson.
            return [l for l in kept if isinstance(l, str) and l in cand_set][:cap]
    except Exception as e:
        print(f"    curate_lessons error: {e}")
    # Fallback: keep the newest `cap` lessons (FIFO behavior preserved on failure)
    return candidates[:cap]


async def synthesise_lessons(client, reflections: list[dict], date_str: str) -> list[str]:
    """
    Synthesise durable lessons from all reflections.

    Produces up to 8 lessons total, weighted by what actually emerged from the
    day's results — no enforced split. Lesson types are CONTINUE (reasoning
    that worked), CHANGE (reasoning that failed), and WATCH (emerging patterns
    not yet ready to act on). On a sweep day this might be 6 CONTINUE / 1 CHANGE
    / 1 WATCH; on a rough day it might be 0 / 6 / 2. The mix reflects the
    races, not a quota.
    """
    continues = [r for r in reflections if r.get("lesson_type") == "continue"]
    changes = [r for r in reflections if r.get("lesson_type") == "change"]

    def _fmt(items, n=25):
        return "\n".join(
            f"  - [{r.get('factor','')}] {r.get('lesson','')}"
            for r in items[:n]
        ) or "  (none)"

    prompt = (
        f"You are Secretariat synthesising what you learned on {date_str}.\n\n"
        f"REASONING THAT WORKED ({len(continues)} races):\n{_fmt(continues)}\n\n"
        f"REASONING THAT FAILED ({len(changes)} races):\n{_fmt(changes)}\n\n"
        "The per-race reflections above already incorporate the official results — "
        "top-3 W/P/S payoffs and exotic wager payoffs. Weigh that context as you synthesise: "
        "a string of correct picks at $4.00 chalk prices is a different lesson than three live "
        "$15+ winners; a miss where the trifecta paid $800 is a different lesson than one where "
        "it paid $40.\n\n"
        "Produce up to 8 lessons total that I will carry into every future race I handicap.\n"
        "Lesson types — choose freely based on what actually emerged today, no enforced split:\n"
        "- CONTINUE: a pattern from correct picks that's worth continuing to trust\n"
        "- CHANGE:   a specific adjustment to make based on a failure\n"
        "- WATCH:    an emerging pattern worth monitoring but not yet acting on\n\n"
        "Lessons about value (price-aware betting) and exotic structuring (when my P/S picks "
        "formed — or could have formed — a hittable exacta/trifecta) are welcome and often more "
        "actionable than pure win-rate observations.\n\n"
        "Only write a lesson when something genuine emerged — do not invent lessons "
        "to fill a quota. A quiet day might warrant 2-3 lessons; a noisy day might "
        "warrant 8. Skew the mix toward whichever type the day actually produced.\n\n"
        "NEVER write a lesson about confusing or misidentifying horses, or about "
        "'verifying horse identity / the correct runner' — picks come from the exact "
        "runner list, so name confusion is not a real failure mode. A winner whose "
        "name resembles one of my picks is a handicapping miss, not an identity mixup. "
        "Drop any such reasoning and reflect on the verifiable factor instead "
        "(pace, class, form, price, post, pace shape).\n\n"
        "DURABILITY OVER RECENCY — the most important constraint. These lessons feed "
        "directly into how I handicap every future race, so they must be TRUE PATTERNS, "
        "not reactions to one day's variance:\n"
        "- A single day's box score is noise. NEVER build a rule on a small sample like "
        "'0-for-10 today', '2/9 on one card', or '3/8 in a week' — results that small swing "
        "on luck alone, and a rule built on them just chases randomness. Form a rule only "
        "when the pattern would plausibly hold over many races, not because today ran hot or cold.\n"
        "- Prefer GENERAL, transferable handicapping principles (pace shape, class moves, "
        "value vs the market, running-style/pace fit, post/bias) over hyper-specific micro-rules "
        "bolted to one track + surface + race-type. A principle that travels beats a rule for "
        "'Allowance races at one track' that I'll almost never get to re-test.\n"
        "- Every lesson must encode PREDICTIVE knowledge I can apply to a future race. Do NOT "
        "write meta-commentary about my own process: no 'I'm still not applying my lesson', no "
        "'this is still unproven', no restating or grading a prior lesson. If something isn't yet "
        "proven, leave it out — an unproven hunch is not a lesson.\n\n"
        "Each lesson must be specific, actionable, generalizable, and written in first person.\n"
        "Format each as: 'CONTINUE: When...', 'CHANGE: When...', 'WATCH: When...'\n\n"
        'Return ONLY a JSON array of strings (between 1 and 8 items).'
    )

    try:
        from app.core.llm_cost import tracked_create
        resp = await tracked_create(
            client,
            endpoint="nightly_reflect_synthesise",
            model="claude-sonnet-4-6",
            max_tokens=1200,
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
    import ssl

    import anthropic
    import httpx
    from sqlalchemy import select, update

    from app.core import database as _db
    from app.core.config import settings
    from app.models.accuracy import RacePrediction, SecretariatCalibration

    await _db.init_db()
    await _ensure_columns(_db._engine)

    ssl_ctx = ssl.create_default_context()
    client = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        http_client=httpx.AsyncClient(verify=ssl_ctx),
    )

    print(f"\n[nightly_reflect] Reflecting on {target_date} | dry_run={dry_run}")

    # 1. Load NA-only settled predictions for target_date that haven't been
    # reflected yet. The reflection IS NULL filter makes re-runs cheap: a
    # restart-triggered catchup or manual backfill skips rows we've already
    # paid Claude to reflect on.
    async with _db._AsyncSessionLocal() as db:
        result = await db.execute(
            select(RacePrediction).where(
                RacePrediction.race_date == target_date,
                RacePrediction.result_fetched == True,  # noqa: E712
                RacePrediction.reflection.is_(None),
                (RacePrediction.region == "na") | (RacePrediction.region == None),  # noqa: E711
            )
        )
        predictions = result.scalars().all()

    if not predictions:
        print("No unreflected settled predictions for target_date — exiting.")
        return

    total = len(predictions)
    hits = sum(1 for p in predictions if p.top_pick_correct)
    misses = total - hits
    print(f"  {total} settled predictions: {hits} correct, {misses} missed")

    # 1b. Fetch official results for the same date so reflections include
    # the wagers and payoffs (top-3 W/P/S + exotic payoffs), not just names.
    # Cached by racing_api, so re-running is cheap.
    from app.services.racing_api import get_na_results_full
    results_by_id: dict = {}
    try:
        na_data = await get_na_results_full(target_date.isoformat())
        results_by_id = {
            r.get("race_id"): r
            for r in na_data.get("results", [])
            if r.get("race_id")
        }
        print(f"  Loaded official results for {len(results_by_id)} races (W/P/S + exotic payoffs).")
    except Exception as e:
        print(f"  ⚠️  Result fetch failed — lessons will lack payoff context: {e}")

    def _money(v) -> str | None:
        if v in (None, "", 0, "0", "0.00"):
            return None
        try:
            return f"${float(v):,.2f}"
        except (TypeError, ValueError):
            return f"${v}"

    def _build_finish_str(result: dict) -> str:
        """1) Horse $win/$place/$show  2) ...  3) ..."""
        if not result:
            return ""
        parts = []
        for r in (result.get("runners") or [])[:3]:
            name = r.get("horse_name") or r.get("horse") or ""
            if not name:
                continue
            pos = r.get("position") or len(parts) + 1
            prices = [
                _money(r.get("win_payoff")),
                _money(r.get("place_payoff")),
                _money(r.get("show_payoff")),
            ]
            price_str = "/".join(p for p in prices if p) or "no payoff"
            parts.append(f"{pos}) {name} {price_str}")
        return "  ".join(parts)

    def _build_exotic_str(result: dict) -> str:
        """Compact exotic-payoff line; skips W/P/S and prop bets."""
        if not result:
            return ""
        skip = {"WIN", "PLACE", "SHOW", "ODD OR EVEN", ""}
        out = []
        for p in (result.get("payoffs") or []):
            name = (p.get("wager_name") or "").strip()
            if name.upper() in skip:
                continue
            amt = _money(p.get("payoff_amount"))
            if not amt:
                continue
            out.append(f"{name} {amt}")
        return ", ".join(out)

    # 2. Build race dicts for reflection (now with payoff context)
    race_dicts = []
    for p in predictions:
        result = results_by_id.get(p.race_id) or {}
        race_dicts.append({
            "race_id": p.race_id,
            "race_name": p.race_name or p.race_id,
            "track": p.track_code or "?",
            "surface": p.surface or "?",
            "race_type": p.race_type or "?",
            "predicted": p.predicted_first or "?",
            "predicted_second": p.predicted_second or "",
            "predicted_third": p.predicted_third or "",
            "place_pick_correct": bool(getattr(p, "place_pick_correct", False)),
            "show_pick_correct": bool(getattr(p, "show_pick_correct", False)),
            "actual": p.actual_first or "?",
            "actual_second": p.actual_second or "",
            "actual_third": p.actual_third or "",
            "hit": bool(p.top_pick_correct),
            "db_id": p.id,
            "finish_str": _build_finish_str(result),
            "exotic_str": _build_exotic_str(result),
        })

    # 3. Batch reflection calls (Haiku — cheap)
    all_reflections: list[dict] = []
    for i in range(0, len(race_dicts), BATCH_SIZE):
        batch = race_dicts[i: i + BATCH_SIZE]
        print(f"  Reflecting batch {i // BATCH_SIZE + 1}/{(len(race_dicts) + BATCH_SIZE - 1) // BATCH_SIZE}…")
        results = await reflect_batch(client, batch)

        # Merge factor/lesson/lesson_type back into race_dicts. lesson_type is
        # required: synthesise_lessons buckets reflections into continue/change
        # by it, so dropping it here leaves synthesise with empty buckets and it
        # produces zero lessons. Fall back to deriving it from the hit flag when
        # the model omits it.
        keyed = {r.get("race_id"): r for r in results}
        for rd in batch:
            match = keyed.get(rd["race_id"])
            if match:
                rd["factor"] = match.get("factor", "")
                rd["lesson"] = match.get("lesson", "")
                rd["lesson_type"] = match.get("lesson_type") or ("continue" if rd.get("hit") else "change")
            else:
                rd["factor"] = ""
                rd["lesson"] = ""
                rd["lesson_type"] = "continue" if rd.get("hit") else "change"
        all_reflections.extend(batch)
        await asyncio.sleep(0.5)  # gentle rate limit

    # Coverage guard: if we had races to reflect on but the batch calls produced
    # zero usable reflections, the learning loop is broken (truncation, parse
    # failure, API error) — fail loudly instead of silently writing nothing.
    reflected = sum(1 for rd in all_reflections if rd.get("lesson"))
    print(f"  Reflections produced: {reflected}/{len(all_reflections)}")
    if all_reflections and reflected == 0:
        print(
            "  ❌ [REFLECT FAILED] 0 reflections produced from "
            f"{len(all_reflections)} settled races — batch calls returned nothing. "
            "Lessons will NOT update. Check reflect_batch truncation / API errors above."
        )
        sys.exit(1)

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
        print(
            "  ❌ [REFLECT FAILED] synthesise produced 0 lessons despite "
            f"{reflected} reflections — calibration NOT updated."
        )
        sys.exit(1)

    print(f"\n  📚 {len(lessons)} lessons for future predictions:")
    for i, lesson in enumerate(lessons, 1):
        print(f"    {i}. {lesson}")

    # 6. Curate against 7-day trend data, then save.
    #    Old behavior: prepend today's, FIFO-cap at 30. That let stale lessons
    #    targeting categories the model wasn't actually improving in sit in the
    #    prompt for weeks. New behavior: merge + curate against trends, hard cap
    #    at 15. Quality over recency.
    if not dry_run:
        async with _db._AsyncSessionLocal() as db:
            cal = await db.get(SecretariatCalibration, 1)
            if cal:
                existing = cal.lessons or []
                merged = lessons + [l for l in existing if l not in lessons]

                from app.services.secretariat import _compute_category_trends
                trends = await _compute_category_trends(target_date, lookback_days=7)
                trends_block = trends.get("block", "")

                curated = await curate_lessons(client, merged, trends_block, date_str)
                dropped = len(merged) - len(curated)
                print(f"  Curated playbook: {len(merged)} candidates → {len(curated)} kept ({dropped} retired).")

                cal.lessons = curated
                cal.updated_at = datetime.datetime.now(datetime.timezone.utc)
            else:
                # No calibration row yet — create one with just today's lessons.
                # Curation kicks in from day 2 onward when there's something to merge.
                from app.models.accuracy import SecretariatCalibration as _Cal
                db.add(_Cal(
                    id=1,
                    updated_at=datetime.datetime.now(datetime.timezone.utc),
                    rolling_win_rate=0.0,
                    sample_size=0,
                    lessons=lessons,
                ))
            await db.commit()
        print(f"\n✅ SecretariatCalibration.lessons updated ({len(lessons)} new this run).")

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
