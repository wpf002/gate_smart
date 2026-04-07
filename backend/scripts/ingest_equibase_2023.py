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
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile

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
    """Unique identifier for a horse-race result."""
    return f"{result['race_date']}|{result['track_code']}|{result['race_number']}|{result['horse_name_key']}"


def store_horse_result(r: redis_lib.Redis, result: dict) -> bool:
    """
    Merge a single result into equibase:horse:{horse_name_key}.
    Returns True if a new record was added, False if it was a duplicate.
    """
    key = f"equibase:horse:{result['horse_name_key']}"
    raw = r.get(key)
    existing: list = json.loads(raw) if raw else []

    existing_keys = {_dedup_key(e) for e in existing}
    new_key = _dedup_key(result)
    if new_key in existing_keys:
        return False

    existing.append(result)
    # Sort newest first by race_date
    existing.sort(key=lambda x: x.get("race_date", ""), reverse=True)
    # Cap at 20
    existing = existing[:20]

    r.set(key, json.dumps(existing))
    return True


def store_chart_result(r: redis_lib.Redis, result: dict) -> None:
    """
    Merge a single result into equibase:chart:{track_code}:{race_date}.
    Dedup by race_number + horse_name_key.
    """
    track_code = (result["track_code"] or "UNK").upper()
    race_date = result["race_date"] or "0000-00-00"
    key = f"equibase:chart:{track_code}:{race_date}"

    raw = r.get(key)
    existing: list = json.loads(raw) if raw else []

    existing_keys = {f"{e['race_number']}|{e['horse_name_key']}" for e in existing}
    entry_key = f"{result['race_number']}|{result['horse_name_key']}"
    if entry_key in existing_keys:
        return

    existing.append(result)
    r.set(key, json.dumps(existing))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Equibase 2023 result charts into Redis")
    parser.add_argument("--zip", required=True, help="Path to the result charts ZIP file")
    parser.add_argument("--limit", type=int, default=None, help="Max number of XML files to process")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to Redis")
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

        # Collect all XML files, skip __MACOSX junk
        xml_files = []
        for root_dir, dirs, files in os.walk(tmpdir):
            # Skip Mac resource fork directories
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

        # For dry-run reporting
        dry_run_samples: list[dict] = []

        for i, xml_path in enumerate(xml_files, 1):
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
                    try:
                        added = store_horse_result(r, result)
                        if added:
                            horses_stored += 1
                        store_chart_result(r, result)
                    except Exception as e:
                        print(f"  ERROR storing {result.get('horse_name', '?')}: {e}")
                        errors += 1

            files_processed += 1

            if files_processed % 100 == 0:
                print(f"Processed {files_processed}/{len(xml_files)} files | "
                      f"horses_stored={horses_stored} | "
                      f"speed_ratings={speed_ratings_found} | "
                      f"errors={errors}")

        # Final summary
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
                print(f"    key         : {s['horse_name_key']}")
                print(f"    track       : {s['track_name']} ({s['track_code']})")
                print(f"    date        : {s['race_date']}  race #{s['race_number']}")
                print(f"    type        : {s['race_type']}")
                print(f"    distance    : {s['distance']}")
                print(f"    surface     : {s['surface']} ({s['course_desc']})")
                print(f"    condition   : {s['track_condition']}")
                print(f"    finish      : {s['official_finish']}")
                print(f"    speed_rating: {s['speed_rating']}")
                print(f"    jockey      : {s['jockey_first']} {s['jockey_last']}")
                print(f"    trainer     : {s['trainer_first']} {s['trainer_last']}")


if __name__ == "__main__":
    main()
