"""
Ingest DRF text chart files into Postgres.

DRF sells comma-delimited chart files covering all North American racing back to
January 1993, as an unlimited monthly subscription. That is the only route we
found to pre-2023 US history that needs no agreement with anyone: it is a shop
checkout, not a data partnership.

These charts carry things nothing else we hold does — running position and
lengths at every point of call, a trouble flag, exotic payoffs per race, and
stable jockey/trainer keys that survive spelling changes.

Usage:
    cd backend
    python scripts/ingest_drf_charts.py --dir "/path/to/drf_charts" --dry-run --limit 2
    python scripts/ingest_drf_charts.py --dir "/path/to/drf_charts"
    python scripts/ingest_drf_charts.py --zip /path/to/2019_charts.zip

Start with --dry-run: it parses and prints without writing, so the layout can be
checked against a real file before a full load. The field map below is DRF's
published spec (Text Chart Data Fields v2.0, 30/03/2011); if a future file
disagrees, --dry-run is where that shows up.

Data destination: tables drf_chart_races and drf_chart_starters, created on
first run. Re-running is safe — a race or starter already present is skipped.
Set DATABASE_URL to write to production.
"""
import argparse
import csv
import glob
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import psycopg2
import psycopg2.extras

from app.core.config import settings

# Record type is always field 1. DRF ships one file per card with these mixed.
REC_HEADER, REC_RACE, REC_STARTER = "H", "R", "S"
REC_EXOTIC, REC_ATTENDANCE, REC_COMMENT, REC_FOOTNOTE = "E", "A", "C", "F"

# ── Field positions, 1-indexed as the spec numbers them ─────────────────────
H = {"country": 2, "track_code": 3, "race_date": 4, "races_on_card": 5,
     "day_evening": 6, "track_name": 7}

R = {"race_number": 2, "breed": 3, "race_type": 4, "restrictions": 5,
     "sex_restriction": 6, "age_restriction": 7, "purse": 9,
     "claim_min": 27, "claim_max": 28, "about_distance": 29, "distance": 30,
     "distance_unit": 31, "surface": 32, "course_type": 33, "num_horses": 34,
     "grade": 35, "race_name": 36, "post_time": 38, "off_time": 40,
     "race_class_codes": 42, "track_condition": 43, "off_turf": 44,
     "track_variant": 45, "drf_speed": 46, "final_time": 51,
     "fraction_1": 52, "fraction_2": 53, "fraction_3": 54, "fraction_4": 55,
     "fraction_5": 56, "wps_pool": 59, "weather": 61, "official": 64}

S = {"race_number": 2, "horse_key": 3, "horse_name": 4, "foaling_date": 5,
     "area_foaled": 6, "breed": 7, "sex": 8, "color": 9,
     "dam": 10, "sire": 13, "broodmare_sire": 16, "sires_sire": 19,
     "weight_carried": 22, "horse_weight": 23, "medications": 24,
     "equipment": 25, "earnings": 26,
     "jockey_last": 27, "jockey_first": 28, "apprentice": 30,
     "trainer_last": 31, "trainer_first": 32,
     "owner_last": 34, "owner_first": 35,
     "odds": 37, "favorite": 41, "post_position": 42, "program_number": 43,
     "pos_start": 44, "pos_c1": 45, "pos_c2": 46, "pos_c3": 47, "pos_c4": 48,
     "pos_c5": 49, "original_finish": 50, "official_finish": 51,
     "ahead_c1": 52, "ahead_c2": 53, "ahead_c3": 54, "ahead_c4": 55,
     "ahead_c5": 56, "ahead_finish": 57,
     "behind_c1": 58, "behind_c2": 59, "behind_c3": 60, "behind_c4": 61,
     "behind_c5": 62, "behind_finish": 63,
     "dead_heat": 64, "claim_price": 65,
     "short_comment": 66, "long_comment": 67,
     "win_payoff": 68, "place_payoff": 69, "show_payoff": 70,
     "claimed": 71, "scratch_reason": 82, "dq_indicator": 83,
     "dq_placing": 84, "trouble": 85, "speed_index": 89, "breeder": 90,
     "jockey_key": 91, "trainer_key": 92}

E = {"race_number": 2, "wager_type": 3, "wagering": 4, "winning_numbers": 5,
     "minimum": 6, "pool_total": 7, "payoff": 8, "carryover": 9}

DDL = """
CREATE TABLE IF NOT EXISTS drf_chart_races (
    id SERIAL PRIMARY KEY,
    track_code TEXT NOT NULL, track_name TEXT, country TEXT,
    race_date DATE NOT NULL, race_number INTEGER NOT NULL,
    day_evening TEXT, breed TEXT, race_type TEXT, restrictions TEXT,
    sex_restriction TEXT, age_restriction TEXT, grade TEXT, race_name TEXT,
    purse NUMERIC, claim_min NUMERIC, claim_max NUMERIC,
    distance NUMERIC, distance_unit TEXT, about_distance TEXT,
    surface TEXT, course_type TEXT, num_horses INTEGER,
    track_condition TEXT, off_turf TEXT, weather TEXT,
    track_variant NUMERIC, drf_speed NUMERIC,
    post_time TEXT, off_time TEXT, final_time NUMERIC,
    fraction_1 NUMERIC, fraction_2 NUMERIC, fraction_3 NUMERIC,
    fraction_4 NUMERIC, fraction_5 NUMERIC,
    wps_pool NUMERIC, race_class_codes TEXT, official TEXT,
    exotics JSONB,
    UNIQUE (track_code, race_date, race_number)
);

CREATE TABLE IF NOT EXISTS drf_chart_starters (
    id SERIAL PRIMARY KEY,
    track_code TEXT NOT NULL, race_date DATE NOT NULL,
    race_number INTEGER NOT NULL,
    horse_key TEXT, horse_name TEXT NOT NULL, horse_name_key TEXT,
    foaling_date TEXT, area_foaled TEXT, breed TEXT, sex TEXT, color TEXT,
    dam TEXT, sire TEXT, broodmare_sire TEXT, sires_sire TEXT, breeder TEXT,
    weight_carried NUMERIC, horse_weight NUMERIC,
    medications TEXT, equipment TEXT, earnings NUMERIC,
    jockey_first TEXT, jockey_last TEXT, jockey_key TEXT, apprentice TEXT,
    trainer_first TEXT, trainer_last TEXT, trainer_key TEXT,
    owner_first TEXT, owner_last TEXT,
    odds NUMERIC, favorite TEXT, post_position INTEGER, program_number TEXT,
    pos_start INTEGER, pos_c1 INTEGER, pos_c2 INTEGER, pos_c3 INTEGER,
    pos_c4 INTEGER, pos_c5 INTEGER,
    original_finish INTEGER, official_finish INTEGER,
    ahead_c1 NUMERIC, ahead_c2 NUMERIC, ahead_c3 NUMERIC, ahead_c4 NUMERIC,
    ahead_c5 NUMERIC, ahead_finish NUMERIC,
    behind_c1 NUMERIC, behind_c2 NUMERIC, behind_c3 NUMERIC, behind_c4 NUMERIC,
    behind_c5 NUMERIC, behind_finish NUMERIC,
    dead_heat TEXT, claim_price NUMERIC, claimed TEXT,
    short_comment TEXT, long_comment TEXT,
    win_payoff NUMERIC, place_payoff NUMERIC, show_payoff NUMERIC,
    scratch_reason TEXT, dq_indicator TEXT, dq_placing INTEGER,
    trouble TEXT, speed_index NUMERIC,
    UNIQUE (track_code, race_date, race_number, horse_name_key)
);

CREATE INDEX IF NOT EXISTS ix_drf_starters_horse ON drf_chart_starters (horse_name_key, race_date);
CREATE INDEX IF NOT EXISTS ix_drf_starters_trainer ON drf_chart_starters (lower(trainer_last), lower(trainer_first));
CREATE INDEX IF NOT EXISTS ix_drf_starters_jockey ON drf_chart_starters (lower(jockey_last), lower(jockey_first));
CREATE INDEX IF NOT EXISTS ix_drf_races_date ON drf_chart_races (race_date);
"""


def _f(row: list, pos: int):
    """One field by its 1-indexed spec position, or None when absent/blank."""
    if pos - 1 >= len(row):
        return None
    v = (row[pos - 1] or "").strip()
    return v or None


def _num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


def _date(v):
    """CCYYMMDD -> ISO, which is how every date in these files is written."""
    if not v or len(str(v)) != 8 or not str(v).isdigit():
        return None
    s = str(v)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _horse_key(name: str) -> str:
    import re
    cleaned = re.sub(r"['’.]", "", (name or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", cleaned)).strip()[:160]


def parse_card(path: str) -> tuple[list, list]:
    """One chart file -> (races, starters). Unknown record types are ignored."""
    header, races, starters, exotics = {}, {}, [], {}
    with open(path, newline="", encoding="latin-1") as fh:
        for row in csv.reader(fh):
            if not row:
                continue
            kind = (row[0] or "").strip().upper()
            if kind == REC_HEADER:
                header = {
                    "country": _f(row, H["country"]),
                    "track_code": _f(row, H["track_code"]),
                    "race_date": _date(_f(row, H["race_date"])),
                    "day_evening": _f(row, H["day_evening"]),
                    "track_name": _f(row, H["track_name"]),
                }
            elif kind == REC_RACE:
                num = _int(_f(row, R["race_number"]))
                if num is None:
                    continue
                rec = {k: _f(row, pos) for k, pos in R.items()}
                for k in ("purse", "claim_min", "claim_max", "distance", "track_variant",
                          "drf_speed", "final_time", "fraction_1", "fraction_2",
                          "fraction_3", "fraction_4", "fraction_5", "wps_pool"):
                    rec[k] = _num(rec.get(k))
                rec["race_number"] = num
                rec["num_horses"] = _int(rec.get("num_horses"))
                rec.update(header)
                races[num] = rec
            elif kind == REC_STARTER:
                num = _int(_f(row, S["race_number"]))
                name = _f(row, S["horse_name"])
                if num is None or not name:
                    continue
                rec = {k: _f(row, pos) for k, pos in S.items()}
                for k in ("weight_carried", "horse_weight", "earnings", "odds",
                          "claim_price", "win_payoff", "place_payoff", "show_payoff",
                          "speed_index", "ahead_c1", "ahead_c2", "ahead_c3", "ahead_c4",
                          "ahead_c5", "ahead_finish", "behind_c1", "behind_c2",
                          "behind_c3", "behind_c4", "behind_c5", "behind_finish"):
                    rec[k] = _num(rec.get(k))
                for k in ("post_position", "pos_start", "pos_c1", "pos_c2", "pos_c3",
                          "pos_c4", "pos_c5", "original_finish", "official_finish",
                          "dq_placing"):
                    rec[k] = _int(rec.get(k))
                rec["race_number"] = num
                rec["horse_name"] = name
                rec["horse_name_key"] = _horse_key(name)
                rec["track_code"] = header.get("track_code")
                rec["race_date"] = header.get("race_date")
                starters.append(rec)
            elif kind == REC_EXOTIC:
                num = _int(_f(row, E["race_number"]))
                if num is None:
                    continue
                exotics.setdefault(num, []).append({
                    "wager_type": _f(row, E["wager_type"]),
                    "winning_numbers": _f(row, E["winning_numbers"]),
                    "minimum": _num(_f(row, E["minimum"])),
                    "pool_total": _num(_f(row, E["pool_total"])),
                    "payoff": _num(_f(row, E["payoff"])),
                    "carryover": _num(_f(row, E["carryover"])),
                })
    for num, rec in races.items():
        rec["exotics"] = exotics.get(num)
    ok = [r for r in races.values() if r.get("track_code") and r.get("race_date")]
    return ok, [s for s in starters if s.get("track_code") and s.get("race_date")]


def _insert(cur, table: str, rows: list, conflict: str) -> int:
    if not rows:
        return 0
    cols = sorted({k for r in rows for k in r})
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s "
           f"ON CONFLICT ({conflict}) DO NOTHING")
    values = [tuple(
        psycopg2.extras.Json(r.get(c)) if c == "exotics" and r.get(c) is not None
        else r.get(c) for c in cols
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, values, page_size=500)
    return cur.rowcount


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest DRF text charts into Postgres")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", help="Directory of chart files")
    src.add_argument("--zip", help="ZIP of chart files")
    ap.add_argument("--limit", type=int, help="Only process this many files")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse and print without writing — run this first")
    args = ap.parse_args()

    tmp = None
    if args.zip:
        tmp = tempfile.mkdtemp(prefix="drf_charts_")
        with zipfile.ZipFile(args.zip) as z:
            z.extractall(tmp)
        root = tmp
    else:
        root = args.dir

    files = sorted(f for f in glob.glob(os.path.join(root, "**", "*"), recursive=True)
                   if os.path.isfile(f) and not f.lower().endswith(".zip"))
    if args.limit:
        files = files[:args.limit]
    if not files:
        print(f"No chart files under {root}")
        return
    print(f"{len(files)} file(s) to process")

    conn = cur = None
    if not args.dry_run:
        conn = psycopg2.connect(settings.DATABASE_URL.replace("+asyncpg", ""))
        cur = conn.cursor()
        cur.execute(DDL)
        conn.commit()

    races_in = starters_in = 0
    for i, path in enumerate(files, 1):
        try:
            races, starters = parse_card(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {os.path.basename(path)}: {type(e).__name__}: {e}")
            continue
        if args.dry_run:
            print(f"\n=== {os.path.basename(path)}: {len(races)} races, {len(starters)} starters")
            if races:
                r = races[0]
                print(f"  race 1: {r.get('track_name')} {r.get('race_date')} "
                      f"R{r.get('race_number')} {r.get('distance')}{r.get('distance_unit')} "
                      f"{r.get('surface')} {r.get('track_condition')} purse {r.get('purse')} "
                      f"variant {r.get('track_variant')} exotics {len(r.get('exotics') or [])}")
            for s in starters[:3]:
                print(f"  {s.get('program_number')} {s.get('horse_name')}: "
                      f"fin {s.get('official_finish')}/{s.get('pos_start')}-"
                      f"{s.get('pos_c1')}-{s.get('pos_c2')}-{s.get('pos_c3')} "
                      f"beaten {s.get('behind_finish')}, odds {s.get('odds')}, "
                      f"{s.get('trainer_first')} {s.get('trainer_last')} / "
                      f"{s.get('jockey_first')} {s.get('jockey_last')} "
                      f"— {s.get('long_comment') or s.get('short_comment')}")
            continue
        races_in += _insert(cur, "drf_chart_races", races,
                            "track_code, race_date, race_number")
        starters_in += _insert(cur, "drf_chart_starters", starters,
                               "track_code, race_date, race_number, horse_name_key")
        conn.commit()
        if i % 50 == 0:
            print(f"  {i}/{len(files)} files — {races_in} races, {starters_in} starters")

    if conn:
        cur.close()
        conn.close()
        print(f"\nDone: {races_in} races, {starters_in} starters written")
    else:
        print("\nDry run — nothing written")
    if tmp:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
