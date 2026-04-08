"""
Ingest TrackMaster 2023 result charts into Postgres.

Usage:
    cd backend
    python scripts/ingest_equibase_2023.py --zip /path/to/2023_Result_Charts.zip
    python scripts/ingest_equibase_2023.py --zip /path/to/2023_Result_Charts.zip --limit 10 --dry-run

Data destination: Postgres table horse_result_charts
  - Duplicate entries (same horse + track + date + race number) are skipped on re-run.
  - Run against production by setting DATABASE_URL env var.
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.services.equibase_api import parse_result_chart

import psycopg2
import psycopg2.extras


INSERT_SQL = """
INSERT INTO horse_result_charts (
    horse_name_key, horse_name,
    track_code, track_name, race_date, race_number, breed, race_type,
    purse, distance, surface, course_desc, track_condition,
    class_rating, win_time, fraction_1, fraction_2, fraction_3, pace_final, footnotes,
    program_num, post_pos, official_finish, speed_rating, weight, age,
    sex_code, sex_desc, meds, equipment, dollar_odds, claim_price,
    jockey_first, jockey_last, jockey_key,
    trainer_first, trainer_last, trainer_key,
    owner, comment, win_payoff, place_payoff, show_payoff, points_of_call
) VALUES (
    %(horse_name_key)s, %(horse_name)s,
    %(track_code)s, %(track_name)s, %(race_date)s, %(race_number)s, %(breed)s, %(race_type)s,
    %(purse)s, %(distance)s, %(surface)s, %(course_desc)s, %(track_condition)s,
    %(class_rating)s, %(win_time)s, %(fraction_1)s, %(fraction_2)s, %(fraction_3)s, %(pace_final)s, %(footnotes)s,
    %(program_num)s, %(post_pos)s, %(official_finish)s, %(speed_rating)s, %(weight)s, %(age)s,
    %(sex_code)s, %(sex_desc)s, %(meds)s, %(equipment)s, %(dollar_odds)s, %(claim_price)s,
    %(jockey_first)s, %(jockey_last)s, %(jockey_key)s,
    %(trainer_first)s, %(trainer_last)s, %(trainer_key)s,
    %(owner)s, %(comment)s, %(win_payoff)s, %(place_payoff)s, %(show_payoff)s, %(points_of_call)s
)
ON CONFLICT ON CONSTRAINT uq_chart_entry DO NOTHING
"""


def get_conn():
    return psycopg2.connect(settings.DATABASE_URL_SYNC)


def bulk_insert(conn, records: list[dict]) -> int:
    if not records:
        return 0
    # Serialize points_of_call list to JSON string for psycopg2
    for r in records:
        if isinstance(r.get("points_of_call"), list):
            r["points_of_call"] = json.dumps(r["points_of_call"])
    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, INSERT_SQL, records, page_size=500)
    conn.commit()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Equibase 2023 result charts into Postgres")
    parser.add_argument("--zip", required=True, help="Path to the result charts ZIP file")
    parser.add_argument("--limit", type=int, default=None, help="Max number of XML files to process")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to Postgres")
    parser.add_argument("--batch", type=int, default=1000, help="Records per DB write batch (default 1000)")
    args = parser.parse_args()

    if not os.path.exists(args.zip):
        print(f"ERROR: ZIP not found: {args.zip}")
        sys.exit(1)

    conn = None
    if not args.dry_run:
        try:
            conn = get_conn()
            print("Connected to Postgres")
        except Exception as e:
            print(f"ERROR: Cannot connect to Postgres: {e}")
            sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting ZIP to {tmpdir} ...")
        with zipfile.ZipFile(args.zip, "r") as zf:
            zf.extractall(tmpdir)

        xml_files = []
        for root_dir, dirs, files in os.walk(tmpdir):
            dirs[:] = [d for d in dirs if d != "__MACOSX"]
            for fname in sorted(files):
                if fname.lower().endswith(".xml"):
                    xml_files.append(os.path.join(root_dir, fname))

        total_files = len(xml_files)
        print(f"Found {total_files} XML files")

        if args.limit:
            xml_files = xml_files[: args.limit]
            print(f"Limiting to {len(xml_files)} files")

        files_processed = 0
        rows_written = 0
        speed_ratings_found = 0
        errors = 0
        dry_run_samples: list[dict] = []
        batch: list[dict] = []

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
                    rows_written += 1
                else:
                    batch.append(result)

            files_processed += 1

            if not args.dry_run and len(batch) >= args.batch:
                rows_written += bulk_insert(conn, batch)
                batch = []
                print(
                    f"Processed {files_processed}/{total_files} files | "
                    f"rows_written={rows_written} | "
                    f"speed_ratings={speed_ratings_found} | errors={errors}",
                    flush=True,
                )

        if not args.dry_run and batch:
            rows_written += bulk_insert(conn, batch)

    if conn:
        conn.close()

    print("\n" + "=" * 60)
    print("DRY RUN — no data written" if args.dry_run else "INGESTION COMPLETE")
    print(f"  Files processed : {files_processed}/{total_files}")
    print(f"  Rows written    : {rows_written}")
    print(f"  Speed ratings   : {speed_ratings_found}")
    print(f"  Errors          : {errors}")
    print("=" * 60)

    if args.dry_run and dry_run_samples:
        print("\nSample records with speed ratings:")
        for s in dry_run_samples:
            print(f"\n  Horse: {s['horse_name']}")
            print(f"    speed_rating={s['speed_rating']}  track={s['track_name']} ({s['track_code']})  date={s['race_date']}")


if __name__ == "__main__":
    main()
