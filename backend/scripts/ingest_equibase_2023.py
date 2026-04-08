"""
Ingest TrackMaster 2023 result chart ZIP into Redis.

Usage:
    cd backend
    python scripts/ingest_equibase_2023.py --zip /path/to/2023_Result_Charts.zip
    python scripts/ingest_equibase_2023.py --zip /path/to/2023_Result_Charts.zip --limit 10 --dry-run
    python scripts/ingest_equibase_2023.py --zip /path/to/2023_Result_Charts.zip --limit 50

Redis key schema:
    equibase:horse:{horse_name_key}    — per-horse list of races, newest first, capped 20
    equibase:chart:{track_code}:{race_date}  — all results for a track on a date

Performance: parses all XML into memory, then bulk-writes via Redis pipeline.
This minimises round-trips and is ~500x faster over a high-latency proxy.
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile
from collections import defaultdict

# Ensure backend package is importable when run from backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis as redis_lib

from app.core.config import settings
from app.services.equibase_api import parse_result_chart


def get_redis_client() -> redis_lib.Redis:
    url = settings.REDIS_URL
    if settings.REDIS_PASSWORD:
        url = url.replace("redis://", f"redis://:{settings.REDIS_PASSWORD}@", 1)
    return redis_lib.Redis.from_url(url, decode_responses=True)


def _dedup_key(result: dict) -> str:
    return f"{result['race_date']}|{result['track_code']}|{result['race_number']}|{result['horse_name_key']}"


def bulk_write(r: redis_lib.Redis, horse_map: dict, chart_map: dict) -> tuple[int, int]:
    """
    Write all accumulated data to Redis using pipelines.
    horse_map: {horse_name_key: [result, ...]}
    chart_map: {f"{track_code}:{race_date}": [result, ...]}
    Returns (horses_written, charts_written).
    """
    # ── Fetch all existing horse keys in one pipeline ──────────────────
    horse_keys = list(horse_map.keys())
    chart_keys = list(chart_map.keys())

    # Batch fetch horse keys
    pipe = r.pipeline(transaction=False)
    for k in horse_keys:
        pipe.get(f"equibase:horse:{k}")
    existing_horse_raws = pipe.execute()

    # Batch fetch chart keys
    pipe = r.pipeline(transaction=False)
    for k in chart_keys:
        pipe.get(f"equibase:chart:{k}")
    existing_chart_raws = pipe.execute()

    # ── Merge new data with existing ───────────────────────────────────
    pipe = r.pipeline(transaction=False)
    horses_written = 0

    for k, raw, new_results in zip(horse_keys, existing_horse_raws, horse_map.values()):
        existing = json.loads(raw) if raw else []
        existing_dedup = {_dedup_key(e) for e in existing}
        added = 0
        for result in new_results:
            if _dedup_key(result) not in existing_dedup:
                existing.append(result)
                existing_dedup.add(_dedup_key(result))
                added += 1
        if added:
            existing.sort(key=lambda x: x.get("race_date", ""), reverse=True)
            existing = existing[:20]
            pipe.set(f"equibase:horse:{k}", json.dumps(existing))
            horses_written += added

    charts_written = 0
    for k, raw, new_results in zip(chart_keys, existing_chart_raws, chart_map.values()):
        existing = json.loads(raw) if raw else []
        existing_dedup = {f"{e['race_number']}|{e['horse_name_key']}" for e in existing}
        added = 0
        for result in new_results:
            ek = f"{result['race_number']}|{result['horse_name_key']}"
            if ek not in existing_dedup:
                existing.append(result)
                existing_dedup.add(ek)
                added += 1
        if added:
            pipe.set(f"equibase:chart:{k}", json.dumps(existing))
            charts_written += added

    pipe.execute()
    return horses_written, charts_written


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Equibase 2023 result charts into Redis")
    parser.add_argument("--zip", required=True, help="Path to the result charts ZIP file")
    parser.add_argument("--limit", type=int, default=None, help="Max number of XML files to process")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to Redis")
    parser.add_argument("--batch", type=int, default=200, help="Files per write batch (default 200)")
    args = parser.parse_args()

    if not os.path.exists(args.zip):
        print(f"ERROR: ZIP file not found: {args.zip}")
        sys.exit(1)

    r = None
    if not args.dry_run:
        try:
            r = get_redis_client()
            r.ping()
            print(f"Connected to Redis: {settings.REDIS_URL}")
        except Exception as e:
            print(f"ERROR: Cannot connect to Redis: {e}")
            sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting ZIP to {tmpdir} ...")
        with zipfile.ZipFile(args.zip, "r") as zf:
            zf.extractall(tmpdir)

        xml_files = []
        for root_dir, dirs, files in os.walk(tmpdir):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for fname in files:
                if fname.lower().endswith(".xml"):
                    xml_files.append(os.path.join(root_dir, fname))

        xml_files.sort()
        total_files = len(xml_files)
        print(f"Found {total_files} XML files")

        if args.limit:
            xml_files = xml_files[: args.limit]
            print(f"Limiting to {len(xml_files)} files (--limit {args.limit})")

        files_processed = 0
        horses_stored = 0
        speed_ratings_found = 0
        errors = 0
        dry_run_samples: list[dict] = []

        # Accumulators for current batch
        horse_map: dict[str, list] = defaultdict(list)
        chart_map: dict[str, list] = defaultdict(list)

        for xml_path in xml_files:
            try:
                results = parse_result_chart(xml_path)
            except Exception as e:
                print(f"  ERROR parsing {os.path.basename(xml_path)}: {e}")
                errors += 1
                files_processed += 1
                continue

            for result in results:
                if result.get("speed_rating") is not None:
                    speed_ratings_found += 1

                if args.dry_run:
                    if len(dry_run_samples) < 3 and result.get("speed_rating") is not None:
                        dry_run_samples.append(result)
                    horses_stored += 1
                else:
                    horse_map[result["horse_name_key"]].append(result)
                    chart_key = f"{(result['track_code'] or 'UNK').upper()}:{result['race_date'] or '0000-00-00'}"
                    chart_map[chart_key].append(result)

            files_processed += 1

            # Flush batch every N files
            if not args.dry_run and files_processed % args.batch == 0:
                hw, _ = bulk_write(r, horse_map, chart_map)
                horses_stored += hw
                horse_map = defaultdict(list)
                chart_map = defaultdict(list)
                print(f"Processed {files_processed}/{len(xml_files)} files | "
                      f"horses_stored={horses_stored} | "
                      f"speed_ratings={speed_ratings_found} | "
                      f"errors={errors}", flush=True)

        # Final flush
        if not args.dry_run and (horse_map or chart_map):
            hw, _ = bulk_write(r, horse_map, chart_map)
            horses_stored += hw

        print("\n" + "=" * 60)
        mode_label = "DRY RUN — no data written" if args.dry_run else "INGESTION COMPLETE"
        print(f"{mode_label}")
        print(f"  Files processed : {files_processed}/{len(xml_files)}")
        print(f"  Horses stored   : {horses_stored}")
        print(f"  Speed ratings   : {speed_ratings_found}")
        print(f"  Errors          : {errors}")
        print("=" * 60)

        if args.dry_run and dry_run_samples:
            print("\nSample horses with speed ratings:")
            for s in dry_run_samples:
                print(f"\n  Horse: {s['horse_name']}")
                print(f"    speed_rating: {s['speed_rating']}")
                print(f"    track: {s['track_name']} ({s['track_code']}), {s['race_date']}")


if __name__ == "__main__":
    main()
