"""
Ingest Equibase 2023 Past Performance files into Postgres.

Usage (directory of individual SIMD*.zip files):
    cd backend
    python scripts/ingest_equibase_pps_2023.py --dir "/path/to/2023 PPs"
    python scripts/ingest_equibase_pps_2023.py --dir "/path/to/2023 PPs" --limit 10 --dry-run

Usage (single master ZIP containing nested SIMD ZIPs or XMLs):
    python scripts/ingest_equibase_pps_2023.py --zip /path/to/2023_PPs.zip

Data destination: Postgres table horse_past_performances
  - Duplicate starts (same horse + track + date + race number) are skipped on re-run.
  - Run against production by setting DATABASE_URL env var.
"""
import argparse
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.services.equibase_api import parse_pp_file

import psycopg2
import psycopg2.extras


INSERT_SQL = """
INSERT INTO horse_past_performances (
    horse_name_key, horse_name, registration_number,
    card_date, card_track_code, card_race_number, card_post_time,
    card_distance, card_surface, card_race_type, card_purse, card_breed,
    trainer_first, trainer_last, jockey_first, jockey_last,
    pp_track_code, pp_race_date, pp_race_number, pp_race_type,
    pp_surface, pp_distance, pp_track_condition,
    speed_figure, pace_figure_1, pace_figure_2, pace_figure_3, class_rating,
    official_finish, post_position, field_size,
    earnings_usd, odds_decimal, win_time_hundredths,
    pp_jockey_first, pp_jockey_last,
    short_comment, long_comment
) VALUES (
    %(horse_name_key)s, %(horse_name)s, %(registration_number)s,
    %(card_date)s, %(card_track_code)s, %(card_race_number)s, %(card_post_time)s,
    %(card_distance)s, %(card_surface)s, %(card_race_type)s, %(card_purse)s, %(card_breed)s,
    %(trainer_first)s, %(trainer_last)s, %(jockey_first)s, %(jockey_last)s,
    %(pp_track_code)s, %(pp_race_date)s, %(pp_race_number)s, %(pp_race_type)s,
    %(pp_surface)s, %(pp_distance)s, %(pp_track_condition)s,
    %(speed_figure)s, %(pace_figure_1)s, %(pace_figure_2)s, %(pace_figure_3)s, %(class_rating)s,
    %(official_finish)s, %(post_position)s, %(field_size)s,
    %(earnings_usd)s, %(odds_decimal)s, %(win_time_hundredths)s,
    %(pp_jockey_first)s, %(pp_jockey_last)s,
    %(short_comment)s, %(long_comment)s
)
ON CONFLICT (horse_name_key, pp_track_code, pp_race_date, pp_race_number) DO NOTHING
"""


def get_conn():
    return psycopg2.connect(settings.DATABASE_URL_SYNC)


def bulk_insert(conn, records: list[dict]) -> int:
    if not records:
        return 0
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, INSERT_SQL, records, page_size=500)
    conn.commit()
    return len(records)


def _xml_source(args):
    """
    Yield xml_path strings.
    --dir mode: extract each SIMD*.zip on-demand.
    --zip mode: extract master ZIP to temp dir, then walk.
    """
    if args.zip:
        tmp = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(args.zip, "r") as zf:
                zf.extractall(tmp)
            for root_dir, dirs, files in os.walk(tmp):
                dirs[:] = [d for d in dirs if d != "__MACOSX"]
                for fname in files:
                    if fname.lower().endswith(".zip"):
                        try:
                            with zipfile.ZipFile(os.path.join(root_dir, fname), "r") as nzf:
                                nzf.extractall(root_dir)
                        except Exception as e:
                            print(f"  WARN: {fname}: {e}")
            for root_dir, dirs, files in os.walk(tmp):
                dirs[:] = [d for d in dirs if d != "__MACOSX"]
                for fname in sorted(files):
                    if fname.lower().endswith(".xml") and fname.upper().startswith("SIMD"):
                        yield os.path.join(root_dir, fname)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        zip_files = sorted(
            f for f in os.listdir(args.dir)
            if f.lower().endswith(".zip") and f.upper().startswith("SIMD")
        )
        for zname in zip_files:
            ftmp = tempfile.mkdtemp()
            try:
                with zipfile.ZipFile(os.path.join(args.dir, zname), "r") as zf:
                    zf.extractall(ftmp)
                for root_dir, dirs, files in os.walk(ftmp):
                    dirs[:] = [d for d in dirs if d != "__MACOSX"]
                    for fname in files:
                        if fname.lower().endswith(".xml") and fname.upper().startswith("SIMD"):
                            yield os.path.join(root_dir, fname)
            except Exception as e:
                print(f"  WARN: {zname}: {e}")
            finally:
                import shutil
                shutil.rmtree(ftmp, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Equibase 2023 past performances into Postgres")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip", help="Master ZIP file containing SIMD ZIPs or XMLs")
    src.add_argument("--dir", help="Directory of individual SIMD*.zip files")
    parser.add_argument("--limit", type=int, default=None, help="Max XML files to process")
    parser.add_argument("--dry-run", action="store_true", help="Parse without writing to Postgres")
    parser.add_argument("--batch", type=int, default=500, help="Records per DB write batch (default 500)")
    args = parser.parse_args()

    if args.zip and not os.path.exists(args.zip):
        print(f"ERROR: ZIP not found: {args.zip}")
        sys.exit(1)
    if args.dir and not os.path.isdir(args.dir):
        print(f"ERROR: Directory not found: {args.dir}")
        sys.exit(1)

    conn = None
    if not args.dry_run:
        try:
            conn = get_conn()
            print(f"Connected to Postgres")
        except Exception as e:
            print(f"ERROR: Cannot connect to Postgres: {e}")
            sys.exit(1)

    total_available = (
        sum(1 for f in os.listdir(args.dir) if f.lower().endswith(".zip") and f.upper().startswith("SIMD"))
        if args.dir else "?"
    )
    print(f"Source: {args.dir or args.zip}  |  available: {total_available} files")

    files_processed = 0
    records_written = 0
    speed_figures_found = 0
    errors = 0
    dry_run_samples: list[dict] = []
    batch: list[dict] = []
    limit = args.limit or float("inf")

    for xml_path in _xml_source(args):
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
                records_written += 1
            else:
                batch.append(rec)

        files_processed += 1

        if not args.dry_run and len(batch) >= args.batch:
            records_written += bulk_insert(conn, batch)
            batch = []
            print(
                f"Processed {files_processed}/{total_available} files | "
                f"rows_written={records_written} | "
                f"speed_figures={speed_figures_found} | errors={errors}",
                flush=True,
            )

    if not args.dry_run and batch:
        records_written += bulk_insert(conn, batch)

    if conn:
        conn.close()

    print("\n" + "=" * 60)
    print("DRY RUN — no data written" if args.dry_run else "INGESTION COMPLETE")
    print(f"  Files processed  : {files_processed}/{total_available}")
    print(f"  Rows written     : {records_written}")
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
