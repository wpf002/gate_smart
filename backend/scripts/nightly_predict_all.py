#!/usr/bin/env python3
"""
nightly_predict_all.py — Morning pre-race predictions for all US races.
Runs the full analyze_race (with a Haiku top-4 fallback for oversized fields)
so the morning digest and the race-day live page share the same locked pick.
Runs at 8 AM ET via app.core.scheduler (12:00 UTC). Cost: ~$1.65/day for ~150 races.

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
        "MARKET DISCIPLINE: the lowest-odds runner (the morning-line favorite) is the "
        "single most predictive signal. Make 'first' the favorite UNLESS a specific "
        "factor (pace, class, trip, run-style fit) clearly argues against it. Do not "
        "fade the favorite for 'value' — pick who actually wins.\n"
        "Return ONLY this JSON, no explanation:\n"
        '{"first": "horse_name", "second": "horse_name", '
        '"third": "horse_name", "fourth": "horse_name"}'
    )

    try:
        from app.core.llm_cost import tracked_create
        resp = await tracked_create(
            client,
            endpoint="nightly_predict_all",
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


_BATCH_POLL_SECONDS = 30
_BATCH_TIMEOUT_SECONDS = 45 * 60  # past this, unfinished races fall back to sync


async def run_batch_analyses(client, all_races: list, mode: str) -> dict:
    """Analyze every race in one Message Batch (50% off all tokens).

    Returns {race_id: analysis_dict} for every race that succeeded. Any race
    missing from the map (batch error, timeout, unparseable response) falls back
    to the existing synchronous path in the main loop — the batch can only save
    money, never lose a pick. Requests reuse build_analyze_request, so batch and
    sync produce identical prompts (including the cached system blocks).
    """
    import re as _re

    from app.services.secretariat import (
        build_analyze_request,
        extract_and_store_fair_prices,
        finish_analysis,
        pick_model_for_race,
    )

    # Build one request per race. custom_id must be ^[a-zA-Z0-9_-]{1,64}$.
    requests, id_map = [], {}
    for race, _region in all_races:
        race_id = race.get("race_id") or race.get("id", "")
        if not race_id or not race.get("runners"):
            continue
        custom_id = _re.sub(r"[^a-zA-Z0-9_-]", "_", race_id)[:64]
        if custom_id in id_map:
            continue
        id_map[custom_id] = race_id
        try:
            params = await build_analyze_request(
                {**race, "race_id": race_id}, mode=mode,
                model=pick_model_for_race(race_id),
            )
        except Exception as e:
            print(f"  batch: build failed for {race_id} ({e}); will run sync")
            continue
        requests.append({"custom_id": custom_id, "params": params})

    if not requests:
        return {}

    try:
        batch = await client.messages.batches.create(requests=requests)
    except Exception as e:
        print(f"  batch: submit failed ({type(e).__name__}: {e}) — falling back to sync for all")
        return {}

    print(f"  batch: submitted {len(requests)} races as {batch.id}; polling…", flush=True)
    waited = 0
    while waited < _BATCH_TIMEOUT_SECONDS:
        await asyncio.sleep(_BATCH_POLL_SECONDS)
        waited += _BATCH_POLL_SECONDS
        try:
            batch = await client.messages.batches.retrieve(batch.id)
        except Exception as e:
            print(f"  batch: poll error ({e}); retrying")
            continue
        if batch.processing_status == "ended":
            break
    else:
        print(f"  batch: timed out after {waited}s — consuming whatever finished", flush=True)

    analyses: dict = {}
    try:
        results = client.messages.batches.results(batch.id)
        import inspect
        if inspect.isawaitable(results):
            results = await results
        async for entry in results:
            race_id = id_map.get(entry.custom_id)
            if not race_id or entry.result.type != "succeeded":
                continue
            message = entry.result.message
            usage = getattr(message, "usage", None)
            from app.core.llm_cost import log_call
            await log_call(
                endpoint="analyze_race_batch",
                model=getattr(message, "model", "claude-haiku-4-5-20251001"),
                input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0 if usage else 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0 if usage else 0,
                batch=True,
            )
            try:
                analysis = finish_analysis(message.content[0].text)
            except Exception:
                continue  # unparseable → sync fallback for this race
            if analysis and analysis.get("predicted_finish"):
                analyses[race_id] = analysis
                try:
                    await extract_and_store_fair_prices(race_id, analysis)
                except Exception:
                    pass
    except Exception as e:
        print(f"  batch: results fetch failed ({type(e).__name__}: {e}) — sync fallback for the rest")

    print(f"  batch: {len(analyses)}/{len(requests)} analyses recovered from batch", flush=True)
    return analyses


async def main(target_date: datetime.date, dry_run: bool, limit: int | None = None,
               only_missing: bool = False):
    import ssl

    import anthropic
    import httpx
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.core import database as _db
    from app.core.config import settings
    from app.models.accuracy import RacePrediction

    await _db.init_db()

    # Ensure new columns exist (added after initial table creation)
    from sqlalchemy import text as _text
    async with _db._engine.begin() as _conn:
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS region VARCHAR(10)"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS alert_sent BOOLEAN DEFAULT FALSE"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS post_time_et VARCHAR(10)"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS lock_source VARCHAR(30)"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS top_pick_fair_odds FLOAT"))
        await _conn.execute(_text("ALTER TABLE race_predictions ADD COLUMN IF NOT EXISTS pick_model VARCHAR(60)"))

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

    # Coverage tripwire — surface upstream track drops that even the /entries
    # probe-recovery didn't catch (e.g. a wholesale outage, or a track not yet in
    # the 28-day roster). Compares today's distinct-track count to the trailing
    # 14-day median; a sharp drop prints a loud warning in the run logs so a
    # missing marquee track like Saratoga can never again pass unnoticed.
    try:
        from sqlalchemy import text as _cov_text
        async with _db._AsyncSessionLocal() as _cov_sess:
            _cov_rows = await _cov_sess.execute(
                _cov_text(
                    "SELECT COUNT(DISTINCT split_part(race_id, '_', 1)) AS c "
                    "FROM race_predictions "
                    "WHERE race_date >= :cut AND race_date < :today AND race_id LIKE '%\\_%' "
                    "GROUP BY race_date ORDER BY race_date"
                ),
                {"cut": target_date - datetime.timedelta(days=14), "today": target_date},
            )
            _counts = sorted(r[0] for r in _cov_rows)
        _today_tracks = len({
            (r.get("race_id") or "").split("_", 1)[0]
            for r, _ in na_races if "_" in (r.get("race_id") or "")
        })
        if _counts:
            _median = _counts[len(_counts) // 2]
            if _today_tracks < 0.75 * _median:
                print(f"  ⚠️  COVERAGE WARNING: {_today_tracks} distinct tracks today vs "
                      f"trailing 14-day median {_median}. Upstream may be dropping meets — "
                      f"verify racing_api._recover_missing_na_meets is working.")
            else:
                print(f"  Coverage OK: {_today_tracks} tracks (trailing median {_median}).")
    except Exception as _cov_err:
        print(f"  (coverage check skipped: {_cov_err})")

    # --only-missing: skip races that already have a prediction for this date, so
    # a re-run only backfills the gaps (e.g. tracks the upstream /meets listing
    # dropped at the original run time and that have since been recovered). This
    # keeps a recovery run cheap — it analyzes only the new races — and makes the
    # predictor safe to re-run any time coverage looks short.
    if only_missing:
        from sqlalchemy import select
        async with _db._AsyncSessionLocal() as _db_sess:
            existing_rows = await _db_sess.execute(
                select(RacePrediction.race_id).where(
                    RacePrediction.race_date == target_date,
                    RacePrediction.user_id.is_(None),
                    RacePrediction.analysis_mode == "auto_daily",
                )
            )
            existing_ids = {r[0] for r in existing_rows}
        before = len(all_races)
        all_races = [
            (r, region) for (r, region) in all_races
            if (r.get("race_id") or r.get("id", "")) not in existing_ids
        ]
        print(f"  --only-missing: {len(existing_ids)} already predicted; "
              f"{len(all_races)} of {before} races need backfill.")

    if limit:
        all_races = all_races[:limit]  # testing aid: tiny real run, e.g. --limit 2 --dry-run

    if not all_races:
        print("No races found — exiting.")
        return

    predicted = 0
    skipped = 0
    start_time = time.time()

    # Run the FULL analyze_race at nightly time so the morning digest and the
    # race-day live page show the IDENTICAL pick. The result is written to the
    # same Redis cache key the live route checks (keyed by input fingerprint),
    # so repeat clicks return the locked nightly analysis verbatim — no live
    # LLM call unless inputs (scratch / jockey / ML) actually change.
    from app.core.cache import cache_set as _cache_set
    from app.services.secretariat import analyze_race, compute_input_fingerprint, pick_model_for_race

    # Mode used for the cached analysis. Frontend's default risk tolerance
    # is "medium" (see RaceDetailPage MODES const), so caching under "medium"
    # gives a first-click cache hit for users who haven't changed their
    # default risk setting. Other modes fall through to live re-analysis.
    LOCK_MODE = "medium"

    # Phase 1: analyze the whole card via the Batches API (50% off all tokens).
    # Any race the batch misses falls back to the original sync call below, so
    # this can only reduce cost, never cost us a pick.
    try:
        batch_analyses = await run_batch_analyses(client, all_races, LOCK_MODE)
    except Exception as e:
        print(f"  batch phase failed entirely ({e}); running all races sync")
        batch_analyses = {}

    def _name(d):
        if isinstance(d, dict):
            return d.get("horse_name") or d.get("name") or ""
        return d or ""

    def _num(d):
        if isinstance(d, dict):
            return str(d.get("number") or "").lstrip("#") or None
        return None

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

        # Run the FULL analysis. Fall back to the lightweight Haiku prediction
        # if analyze_race fails (e.g., oversized field), so we never lose a pick.
        analysis = batch_analyses.get(race_id)
        made_sync_call = False
        if analysis is None:
            made_sync_call = True
            try:
                analysis = await analyze_race(
                    {**race, "race_id": race_id}, mode=LOCK_MODE,
                    model=pick_model_for_race(race_id),
                )
            except Exception as e:
                print(f"full analyze failed ({e}); fallback…", end=" ")

        if analysis and analysis.get("predicted_finish"):
            pf_full = analysis["predicted_finish"]
            first = _name(pf_full.get("first"))
            second = _name(pf_full.get("second"))
            third = _name(pf_full.get("third"))
            fourth = _name(pf_full.get("fourth"))
            first_num = _num(pf_full.get("first"))
            lock_source = "nightly"
        else:
            bucket_hint = _format_bucket_hint(track_code, race_type, surface, calibration)
            pf = await predict_race(client, race, bucket_hint=bucket_hint)
            if not pf:
                print("skip (no prediction)")
                skipped += 1
                continue
            first = pf.get("first", "")
            second = pf.get("second")
            third = pf.get("third")
            fourth = pf.get("fourth")
            first_num = None
            lock_source = "nightly_fallback"

        # Guarantee distinct horses across the 4 finish slots. The model
        # occasionally repeats a horse (e.g. first == second), which would render
        # as an impossible Morning Line like "1-1-4-2". Keep first occurrences in
        # order; trailing dupes drop to None rather than fabricate a pick.
        def _norm_pick(n):
            return (n or "").strip().lower().replace("'", "").replace("-", " ")

        _seen, _kept = set(), []
        for _name_val in (first, second, third, fourth):
            _k = _norm_pick(_name_val)
            if not _name_val or not _k or _k in _seen:
                continue
            _seen.add(_k)
            _kept.append(_name_val)
        _kept += [None] * (4 - len(_kept))
        first, second, third, fourth = _kept[0], _kept[1], _kept[2], _kept[3]

        if not first:
            print("skip (no distinct pick)")
            skipped += 1
            continue

        print(f"pick={first}")

        # Capture market context (favorite, pick odds, field size) so we can
        # later measure favorite-agreement and calibration of the picks.
        from app.services.odds import compute_market_context
        # Secretariat's own fair price for the horse it picked. Persisted so
        # value (fair price vs market price) can be measured later — it used to
        # exist only in a 4-hour Redis key and was unrecoverable after that.
        top_pick_fair_odds = None
        if analysis:
            from app.services.odds import parse_odds_to_decimal
            _target = _norm_pick(first)
            for _r in (analysis.get("runners") or []):
                if _norm_pick(_r.get("horse_name") or _r.get("name")) == _target:
                    top_pick_fair_odds = parse_odds_to_decimal(_r.get("fair_odds"))
                    break

        market = compute_market_context(
            race.get("runners") or [], pick_name=first, pick_num=first_num
        )

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

            # Stamp lock metadata + populate the live cache so the race-day
            # page serves THIS analysis verbatim. Same fingerprint logic as
            # the live route — they share the cache.
            if analysis:
                fp = compute_input_fingerprint(race)
                analysis["locked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                analysis["input_fingerprint"] = fp
                analysis["lock_source"] = "nightly"
                cache_key = f"ai_analysis:{race_id}:{LOCK_MODE}:default:{fp}"
                try:
                    await _cache_set(cache_key, analysis, ex=86400)  # 24h
                except Exception as e:
                    print(f"  (cache write failed: {e})", end=" ")

            # Clip every string to its column width. A single oversized value
            # (e.g. a composite race_type from an upstream quirk) must never be
            # able to crash the whole run — see the per-race try/except below.
            def _clip(v, n):
                return v[:n] if isinstance(v, str) else v

            race_type_clipped = _clip(race_type, 120)
            row = {
                "race_id": _clip(race_id, 100),
                "race_date": target_date,
                "track_code": _clip(track_code, 20),
                "race_name": _clip(race_name, 200),
                "race_type": race_type_clipped,
                "surface": _clip(surface, 20),
                "region": _clip(region, 10),
                "analysis_mode": "auto_daily",
                "predicted_first": _clip(first, 120),
                "predicted_first_num": _clip(first_num, 10),
                "predicted_second": _clip(second, 120),
                "predicted_third": _clip(third, 120),
                "predicted_fourth": _clip(fourth, 120),
                "post_time_et": _clip(post_time_et, 10),
                "lock_source": _clip(lock_source, 30),
                "field_size": market["field_size"],
                "top_pick_odds": market["top_pick_odds"],
                "favorite_odds": market["favorite_odds"],
                "favorite_num": _clip(market["favorite_num"], 10),
                "top_pick_is_favorite": market["top_pick_is_favorite"],
                "top_pick_fair_odds": top_pick_fair_odds,
                # Which model produced this pick — the A/B's dependent variable.
                "pick_model": pick_model_for_race(race_id) if lock_source == "nightly" else None,
            }
            from sqlalchemy import or_ as _or_
            from sqlalchemy import update as _update
            try:
                async with _db._AsyncSessionLocal() as db:
                    stmt = pg_insert(RacePrediction).values(**row)
                    stmt = stmt.on_conflict_do_nothing(constraint="uq_race_prediction")
                    await db.execute(stmt)
                    # Backfill race_type on rows that already exist with an empty value.
                    if race_type_clipped:
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
                            .values(race_type=race_type_clipped)
                        )
                    await db.commit()
            except Exception as e:
                # One bad race must not sink the slate. Log, skip, keep going.
                print(f"DB write failed ({type(e).__name__}: {e}); skipping race")
                skipped += 1
                continue

        predicted += 1
        if made_sync_call:
            await asyncio.sleep(1.0)  # rate-limit only live API calls, not batch-served races

    elapsed = time.time() - start_time
    # Observed means: sync full analysis ~$0.028/race; batch + prompt caching ~$0.011.
    batch_served = sum(1 for rid in batch_analyses if rid)
    sync_served = max(0, predicted - batch_served)
    cost_est = batch_served * 0.011 + sync_served * 0.028
    print(f"\n✅ Done: {predicted} predicted ({len(na_races)} NA), {skipped} skipped in {elapsed:.0f}s")
    print(f"   {batch_served} via batch, ~{sync_served} sync. Estimated cost: ~${cost_est:.2f} (exact: llm_call_log)")
    if dry_run:
        print("   [DRY RUN] No rows written.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Morning predict-all races")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="analyze only the first N races (testing)")
    parser.add_argument("--only-missing", action="store_true",
                        help="only predict races not already stored for the date (cheap backfill/recovery re-run)")
    args = parser.parse_args()

    target = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    asyncio.run(main(target_date=target, dry_run=args.dry_run, limit=args.limit,
                     only_missing=args.only_missing))
