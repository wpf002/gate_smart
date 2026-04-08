"""
Ingest Equibase 2023 Past Performance ZIP into Redis.

Usage:
    cd backend
    python scripts/ingest_equibase_pps_2023.py --zip /path/to/2023_PPs.zip
    python scripts/ingest_equibase_pps_2023.py --zip /path/to/2023_PPs.zip --limit 10 --dry-run
    python scripts/ingest_equibase_pps_2023.py --zip /path/to/2023_PPs.zip --limit 50

Redis key schema:
    equibase:pp:{horse_name_key}  — per-horse list of past performance records,
                                    newest first, capped at 30 entries.

Each record contains track, date, race type, surface, distance, speed figure,
pace figures, class rating, finish position, jockey/trainer, and race comment.

Performance: parses all XML into memory, then bulk-writes via Redis pipeline.
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis as redis_lib

from app.core.config import settings
from app.services.equibase_api import parse_pp_file

PP_CAP = 30  # max past performances stored per horse


def get_redis_client() -> redis_lib.Redis:
    url = settings.REDIS_URL
    if settings.REDIS_PASSWORD:
        url = url.replace("redis://", f"redis://:{settings.REDIS_PASSWORD}@", 1)
    return redis_lib.Redis.from_url(url, decode_responses=True)


def _dedup_key(record: dict) -> str:
    return (
        f"{record['pp_race_date']}|{record['pp_track_code']}|"
        f"{record['pp_race_number']}|{record['horse_name_key']}"
    )


def bulk_write(r: redis_lib.Redis, horse_map: dict) -> int:
    """
    Merge new PP records with any existing ones in Redis and write back.
    Returns total new records written.
    """
    horse_keys = list(horse_map.keys())

    pipe = r.pipeline(transaction=False)
    for k in horse_keys:
        pipe.get(f"equibase:pp:{k}")
    existing_raws = pipe.execute()

    pipe = r.pipeline(transaction=False)
    total_written = 0

    for k, raw, new_records in zip(horse_keys, existing_raws, horse_map.values()):
        existing = json.loads(raw) if raw else []
        existing_dedup = {_dedup_key(e) for e in existing}
        added = 0
        for rec in new_records:
            dk = _dedup_key(rec)
            if dk not in existing_dedup:
                existing.append(rec)
                existing_dedup.add(dk)
                added += 1
        if added:
            existing.sort(key=lambda x: x.get("pp_race_date", ""), reverse=True)
            existing = existing[:PP_CAP]
            pipe.set(f"equibase:pp:{k}", json.dumps(existing))
            total_written += added

    pipe.execute()
    return total_written


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Equibase 2023 past performances into Redis")
    parser.add_argument("--zip", required=True, help="Path to the 2023 PPs ZIP file")
    parser.add_argument("--limit", type=int, default=None, help="Max XML files to process")
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

        # Extract any nested ZIPs (each track/day is its own zip inside the master)
        print("Extracting nested ZIPs ...")
        nested_extracted = 0
        for root_dir, dirs, files in os.walk(tmpdir):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for fname in files:
                if fname.lower().endswith(".zip"):
                    nested_zip_path = os.path.join(root_dir, fname)
                    try:
                        with zipfile.ZipFile(nested_zip_path, "r") as nzf:
                            nzf.extractall(root_dir)
                        nested_extracted += 1
                    except Exception as e:
                        print(f"  WARN: could not extract {fname}: {e}")
        if nested_extracted:
            print(f"Extracted {nested_extracted} nested ZIPs")

        xml_files = []
        for root_dir, dirs, files in os.walk(tmpdir):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for fname in files:
                if fname.lower().endswith(".xml") and fname.upper().startswith("SIMD"):
                    xml_files.append(os.path.join(root_dir, fname))

        xml_files.sort()
        total_files = len(xml_files)
        print(f"Found {total_files} PP XML files")

        if args.limit:
            xml_files = xml_files[: args.limit]
            print(f"Limiting to {len(xml_files)} files (--limit {args.limit})")

        files_processed = 0
        records_stored = 0
        speed_figures_found = 0
        errors = 0
        dry_run_samples: list[dict] = []

        horse_map: dict[str, list] = defaultdict(list)

        for xml_path in xml_files:
            try:
                records = parse_pp_file(xml_path)
            except Exception as e:
                print(f"  ERROR parsing {os.path.basename(xml_path)}: {e}")
                errors += 1
                files_processed += 1
                continue

            for rec in records:
                if rec.get("speed_figure") is not None:
                    speed_figures_found += 1

                if args.dry_run:
                    if len(dry_run_samples) < 3 and rec.get("speed_figure") is not None:
                        dry_run_samples.append(rec)
                    records_stored += 1
                else:
                    horse_map[rec["horse_name_key"]].append(rec)

            files_processed += 1

            if not args.dry_run and files_processed % args.batch == 0:
                written = bulk_write(r, horse_map)
                records_stored += written
                horse_map = defaultdict(list)
                print(
                    f"Processed {files_processed}/{len(xml_files)} files | "
                    f"records_stored={records_stored} | "
                    f"speed_figures={speed_figures_found} | "
                    f"errors={errors}",
                    flush=True,
                )

        if not args.dry_run and horse_map:
            written = bulk_write(r, horse_map)
            records_stored += written

        print("\n" + "=" * 60)
        mode_label = "DRY RUN — no data written" if args.dry_run else "INGESTION COMPLETE"
        print(f"{mode_label}")
        print(f"  Files processed  : {files_processed}/{len(xml_files)}")
        print(f"  Records stored   : {records_stored}")
        print(f"  Speed figures    : {speed_figures_found}")
        print(f"  Errors           : {errors}")
        print("=" * 60)

        if args.dry_run and dry_run_samples:
            print("\nSample records with speed figures:")
            for s in dry_run_samples:
                print(f"\n  Horse     : {s['horse_name']}")
                print(f"  Card      : {s['card_track_code']} {s['card_date']} R{s['card_race_number']}")
                print(f"  PP race   : {s['pp_track_code']} {s['pp_race_date']} R{s['pp_race_number']}")
                print(f"  Surface   : {s['pp_surface']}  Distance: {s['pp_distance']}")
                print(f"  Speed fig : {s['speed_figure']}  Finish: {s['official_finish']}")
                print(f"  Comment   : {s['short_comment']}")


if __name__ == "__main__":
    main()
