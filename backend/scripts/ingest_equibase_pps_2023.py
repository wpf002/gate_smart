"""
Ingest Equibase 2023 Past Performance files into Redis.

Usage (directory of individual SIMD*.zip files):
    cd backend
    python scripts/ingest_equibase_pps_2023.py --dir "/path/to/2023 PPs"
    python scripts/ingest_equibase_pps_2023.py --dir "/path/to/2023 PPs" --limit 10 --dry-run

Usage (single master ZIP containing nested SIMD ZIPs or XMLs):
    python scripts/ingest_equibase_pps_2023.py --zip /path/to/2023_PPs.zip

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
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", help="Path to a master ZIP file containing SIMD ZIPs or XMLs")
    src.add_argument("--dir", help="Path to a directory of individual SIMD*.zip files")
    parser.add_argument("--limit", type=int, default=None, help="Max XML files to process")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to Redis")
    parser.add_argument("--batch", type=int, default=200, help="Files per write batch (default 200)")
    args = parser.parse_args()

    if args.zip and not os.path.exists(args.zip):
        print(f"ERROR: ZIP file not found: {args.zip}")
        sys.exit(1)
    if args.dir and not os.path.isdir(args.dir):
        print(f"ERROR: Directory not found: {args.dir}")
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

    def _xml_source():
        """
        Yield (xml_path, cleanup_fn) pairs.

        --zip mode: extract master ZIP to a temp dir once, walk for SIMD XMLs
                    (handles nested ZIPs too), clean up at end.
        --dir mode: iterate SIMD*.zip files one-by-one, extract each to a
                    per-file temp dir, yield XMLs, then delete the temp dir.
                    Never extracts all ZIPs up front — safe for large datasets.
        """
        if args.zip:
            tmp = tempfile.mkdtemp()
            try:
                with zipfile.ZipFile(args.zip, "r") as zf:
                    zf.extractall(tmp)
                # extract any nested ZIPs
                for root_dir, dirs, files in os.walk(tmp):
                    dirs[:] = [d for d in dirs if d != "__MACOSX"]
                    for fname in files:
                        if fname.lower().endswith(".zip"):
                            try:
                                with zipfile.ZipFile(os.path.join(root_dir, fname), "r") as nzf:
                                    nzf.extractall(root_dir)
                            except Exception as e:
                                print(f"  WARN: could not extract {fname}: {e}")
                found = []
                for root_dir, dirs, files in os.walk(tmp):
                    dirs[:] = [d for d in dirs if d != "__MACOSX"]
                    for fname in files:
                        if fname.lower().endswith(".xml") and fname.upper().startswith("SIMD"):
                            found.append(os.path.join(root_dir, fname))
                found.sort()
                yield from ((p, lambda: None) for p in found)
            finally:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            # Individual SIMD*.zip files — extract on demand
            zip_files = sorted(
                f for f in os.listdir(args.dir)
                if f.lower().endswith(".zip") and f.upper().startswith("SIMD")
            )
            for zname in zip_files:
                zpath = os.path.join(args.dir, zname)
                ftmp = tempfile.mkdtemp()
                try:
                    with zipfile.ZipFile(zpath, "r") as zf:
                        zf.extractall(ftmp)
                    for root_dir, dirs, files in os.walk(ftmp):
                        dirs[:] = [d for d in dirs if d != "__MACOSX"]
                        for fname in files:
                            if fname.lower().endswith(".xml") and fname.upper().startswith("SIMD"):
                                yield os.path.join(root_dir, fname), lambda: None
                except Exception as e:
                    print(f"  WARN: could not extract {zname}: {e}")
                finally:
                    import shutil
                    shutil.rmtree(ftmp, ignore_errors=True)

    # Count total available files for progress display
    if args.dir:
        total_available = sum(
            1 for f in os.listdir(args.dir)
            if f.lower().endswith(".zip") and f.upper().startswith("SIMD")
        )
    else:
        total_available = "?"  # unknown until extracted
    print(f"Source: {'ZIP' if args.zip else args.dir}  |  available: {total_available} files")

    files_processed = 0
    records_stored = 0
    speed_figures_found = 0
    errors = 0
    dry_run_samples: list[dict] = []
    horse_map: dict[str, list] = defaultdict(list)
    limit = args.limit or float("inf")

    for xml_path, _ in _xml_source():
        if files_processed >= limit:
            break

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
                f"Processed {files_processed}/{total_available} files | "
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
    print(f"  Files processed  : {files_processed}/{total_available}")
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
