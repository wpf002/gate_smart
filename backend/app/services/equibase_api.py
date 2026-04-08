"""
Equibase / TrackMaster parsers.

Result charts: TrackMaster tchSchema.xsd XML (file naming: {TRK}{yyyymmdd}tch.xml)
Past performances: Equibase simulcast.xsd XML (file naming: SIMD{yyyymmdd}{TRK}_{CTR}.xml)
"""
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)


def _text(element, tag: str, default=None):
    """Get text content of a child tag, returning default if missing."""
    if element is None:
        return default
    child = element.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _int(element, tag: str, default: int = 0) -> int:
    val = _text(element, tag)
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _float(element, tag: str, default: float = 0.0) -> float:
    val = _text(element, tag)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _normalize_horse_name(name: str) -> str:
    return name.strip().title()


def make_horse_name_key(name: str) -> str:
    """Convert a horse name to a Redis-safe lookup key."""
    key = name.lower().replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


def parse_result_chart(xml_path: str) -> list[dict]:
    """
    Parse a single TrackMaster result chart XML file.
    Returns a list of horse result dicts (one per ENTRY per RACE).
    Returns empty list if the file cannot be parsed at all.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Failed to parse XML file {xml_path}: {e}")
        return []

    race_date = root.get("RACE_DATE", "")

    track_el = root.find("TRACK")
    track_code = _text(track_el, "CODE", "")
    # Files use <NAME> but spec example shows <n> — handle both
    track_name = _text(track_el, "NAME") or _text(track_el, "n", "")

    results = []

    for race_el in root.findall("RACE"):
        race_number_str = race_el.get("NUMBER", "0")
        try:
            race_number = int(race_number_str)
        except ValueError:
            race_number = 0

        try:
            breed = _text(race_el, "BREED", "")
            race_type = _text(race_el, "TYPE", "")
            purse = _int(race_el, "PURSE", 0)
            dist_val = _text(race_el, "DISTANCE", "")
            dist_unit = _text(race_el, "DIST_UNIT", "")
            distance = f"{dist_val}{dist_unit}" if dist_val else ""
            surface = _text(race_el, "SURFACE", "")
            course_desc = _text(race_el, "COURSE_DESC", "")
            track_condition = _text(race_el, "TRK_COND", "")
            class_rating = _int(race_el, "CLASS_RATING", 0)
            win_time = _float(race_el, "WIN_TIME", 0.0)
            fraction_1 = _float(race_el, "FRACTION_1", 0.0)
            fraction_2 = _float(race_el, "FRACTION_2", 0.0)
            fraction_3 = _float(race_el, "FRACTION_3", 0.0)
            pace_final = _int(race_el, "PACE_FINAL", 0)
            footnotes = _text(race_el, "FOOTNOTES", "")
        except Exception as e:
            logger.error(f"Error reading race {race_number} metadata in {xml_path}: {e}")
            continue

        for entry_el in race_el.findall("ENTRY"):
            # Files use <NAME> but spec example shows <n> — handle both
            horse_name_raw = _text(entry_el, "NAME") or _text(entry_el, "n")
            if not horse_name_raw:
                continue

            try:
                horse_name = _normalize_horse_name(horse_name_raw)
                horse_name_key = make_horse_name_key(horse_name)

                sex_el = entry_el.find("SEX")
                sex_code = _text(sex_el, "CODE", "")
                sex_desc = _text(sex_el, "DESCRIPTION", "")

                jockey_el = entry_el.find("JOCKEY")
                jockey_first = _text(jockey_el, "FIRST_NAME", "")
                jockey_last = _text(jockey_el, "LAST_NAME", "")
                jockey_key = _text(jockey_el, "KEY", "")

                trainer_el = entry_el.find("TRAINER")
                trainer_first = _text(trainer_el, "FIRST_NAME", "")
                trainer_last = _text(trainer_el, "LAST_NAME", "")
                trainer_key = _text(trainer_el, "KEY", "")

                # Official finish: primary OFFICIAL_FIN, fallback OFL_FINISH
                official_fin_el = entry_el.find("OFFICIAL_FIN")
                if official_fin_el is not None and official_fin_el.text and official_fin_el.text.strip():
                    try:
                        official_finish = int(official_fin_el.text.strip())
                    except ValueError:
                        official_finish = 0
                else:
                    ofl_el = entry_el.find("OFL_FINISH")
                    if ofl_el is not None and ofl_el.text and ofl_el.text.strip():
                        try:
                            official_finish = int(ofl_el.text.strip())
                        except ValueError:
                            official_finish = 0
                    else:
                        official_finish = 0

                # Speed rating — None if missing (never default to 0)
                speed_rating: Optional[int] = None
                sr_el = entry_el.find("SPEED_RATING")
                if sr_el is not None and sr_el.text and sr_el.text.strip():
                    try:
                        speed_rating = int(float(sr_el.text.strip()))
                    except ValueError:
                        speed_rating = None

                points_of_call = []
                for poc_el in entry_el.findall("POINT_OF_CALL"):
                    which = poc_el.get("WHICH", "")
                    pos_el = poc_el.find("POSITION")
                    len_el = poc_el.find("LENGTHS")
                    pos = int(pos_el.text.strip()) if pos_el is not None and pos_el.text else 0
                    lengths = float(len_el.text.strip()) if len_el is not None and len_el.text else 0.0
                    points_of_call.append({"which": which, "position": pos, "lengths": lengths})

                results.append({
                    "horse_name": horse_name,
                    "horse_name_key": horse_name_key,
                    "track_code": track_code,
                    "track_name": track_name,
                    "race_date": race_date,
                    "race_number": race_number,
                    "breed": breed,
                    "race_type": race_type,
                    "purse": purse,
                    "distance": distance,
                    "surface": surface,
                    "course_desc": course_desc,
                    "track_condition": track_condition,
                    "class_rating": class_rating,
                    "win_time": win_time,
                    "fraction_1": fraction_1,
                    "fraction_2": fraction_2,
                    "fraction_3": fraction_3,
                    "pace_final": pace_final,
                    "footnotes": footnotes,
                    "program_num": _text(entry_el, "PROGRAM_NUM", ""),
                    "post_pos": _int(entry_el, "POST_POS", 0),
                    "official_finish": official_finish,
                    "speed_rating": speed_rating,
                    "weight": _int(entry_el, "WEIGHT", 0),
                    "age": _int(entry_el, "AGE", 0),
                    "sex_code": sex_code,
                    "sex_desc": sex_desc,
                    "meds": _text(entry_el, "MEDS", ""),
                    "equipment": _text(entry_el, "EQUIP", ""),
                    "dollar_odds": _float(entry_el, "DOLLAR_ODDS", 0.0),
                    "claim_price": _int(entry_el, "CLAIM_PRICE", 0),
                    "jockey_first": jockey_first,
                    "jockey_last": jockey_last,
                    "jockey_key": jockey_key,
                    "trainer_first": trainer_first,
                    "trainer_last": trainer_last,
                    "trainer_key": trainer_key,
                    "owner": _text(entry_el, "OWNER", ""),
                    "comment": _text(entry_el, "COMMENT", ""),
                    "win_payoff": _float(entry_el, "WIN_PAYOFF", 0.0),
                    "place_payoff": _float(entry_el, "PLACE_PAYOFF", 0.0),
                    "show_payoff": _float(entry_el, "SHOW_PAYOFF", 0.0),
                    "points_of_call": points_of_call,
                })

            except Exception as e:
                logger.error(f"Error parsing entry '{horse_name_raw}' in race {race_number} of {xml_path}: {e}")
                continue

    return results


# ---------------------------------------------------------------------------
# Past Performance parser  (Equibase simulcast.xsd  —  SIMD*.xml files)
# ---------------------------------------------------------------------------

def _pp_text(el, *tags, default=None):
    """Walk a chain of child tags and return the text of the final one."""
    cur = el
    for tag in tags:
        if cur is None:
            return default
        cur = cur.find(tag)
    if cur is None or cur.text is None:
        return default
    return cur.text.strip()


def _pp_int(el, *tags, default: int = 0) -> int:
    val = _pp_text(el, *tags)
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _pp_float(el, *tags, default: float = 0.0) -> float:
    val = _pp_text(el, *tags)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _parse_filename_meta(xml_path: str) -> tuple[str, str, str]:
    """
    Extract (card_date, track_code, country) from SIMD filename.
    SIMD20230101AQU_USA.xml  →  ('2023-01-01', 'AQU', 'USA')
    Returns ('', '', '') on parse failure.
    """
    import os
    fname = os.path.basename(xml_path)
    m = re.match(r"SIMD(\d{4})(\d{2})(\d{2})([A-Z0-9]+)_([A-Z]+)\.xml", fname, re.IGNORECASE)
    if not m:
        return "", "", ""
    card_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    track_code = m.group(4).upper()
    country = m.group(5).upper()
    return card_date, track_code, country


def parse_pp_file(xml_path: str) -> list[dict]:
    """
    Parse a single Equibase past-performance XML file (SIMD*.xml).

    Returns one dict per horse per PastPerformance record.
    Redis key: equibase:pp:{horse_name_key}

    Each record contains:
      horse_name, horse_name_key, registration_number
      card_date, card_track_code          ← the race card this entry was filed for
      pp_track_code, pp_race_date, pp_race_number
      pp_race_type, pp_surface, pp_distance, pp_track_condition
      speed_figure, pace_figure_1/2/3, class_rating
      official_finish, post_position
      jockey_first/last, trainer_first/last (from the entry, i.e. current connections)
      short_comment, long_comment
      earnings_usd, odds_decimal
      win_time_hundredths, field_size
    """
    card_date, card_track_code, _ = _parse_filename_meta(xml_path)

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        logger.error(f"Failed to parse PP XML {xml_path}: {e}")
        return []

    records: list[dict] = []

    for race_el in root.findall("Race"):
        race_number = _pp_int(race_el, "RaceNumber")
        post_time = _pp_text(race_el, "PostTime", default="")
        race_distance = _pp_text(race_el, "Distance", "PublishedValue", default="")
        race_surface = _pp_text(race_el, "Course", "CourseType", "Value", default="")
        race_type = _pp_text(race_el, "RaceType", "RaceType", default="")
        race_purse = _pp_float(race_el, "PurseUSA")
        race_breed = _pp_text(race_el, "BreedType", "Value", default="")

        for starter_el in race_el.findall("Starters"):
            horse_name_raw = _pp_text(starter_el, "Horse", "HorseName")
            if not horse_name_raw:
                continue

            horse_name = _normalize_horse_name(horse_name_raw)
            horse_name_key = make_horse_name_key(horse_name)
            reg_num = _pp_text(starter_el, "Horse", "RegistrationNumber", default="")

            # Current connections (as of the card date)
            trainer_first = _pp_text(starter_el, "Trainer", "FirstName", default="")
            trainer_last = _pp_text(starter_el, "Trainer", "LastName", default="")
            jockey_first = _pp_text(starter_el, "Jockey", "FirstName", default="")
            jockey_last = _pp_text(starter_el, "Jockey", "LastName", default="")

            for pp_el in starter_el.findall("PastPerformance"):
                start_el = pp_el.find("Start")
                if start_el is None:
                    continue

                # Speed / pace / class figures
                # XML stores figures as tenths (e.g. 480 = 48.0); 9999 = no figure sentinel
                def _figure(el, *tags) -> Optional[int]:
                    raw = _pp_int(el, *tags)
                    if raw == 0 or raw >= 9999:
                        return None
                    return round(raw / 10)

                speed_figure = _figure(start_el, "SpeedFigure")
                pace_1 = _figure(start_el, "PaceFigure1") or 0
                pace_2 = _figure(start_el, "PaceFigure2") or 0
                pace_3 = _figure(start_el, "PaceFigure3") or 0
                class_rating = _figure(start_el, "ClassRating") or 0
                official_finish = _pp_int(start_el, "OfficialFinish")
                post_position = _pp_int(start_el, "PostPosition")
                earnings_usd = _pp_float(start_el, "EarningsUSA")

                # Odds stored as integer (e.g. 5875 = 58.75/1); convert to float
                raw_odds = _pp_int(start_el, "Odds")
                odds_decimal = round(raw_odds / 100, 2) if raw_odds else 0.0

                short_comment = _pp_text(start_el, "ShortComment", default="")
                long_comment = _pp_text(start_el, "LongComment", default="")

                # Jockey at time of the past race (may differ from current)
                pp_jockey_first = _pp_text(start_el, "Jockey", "FirstName", default="")
                pp_jockey_last = _pp_text(start_el, "Jockey", "LastName", default="")

                # Win time: Fraction tag with Fraction child = 'W'
                win_time_hundredths = 0
                for frac_el in pp_el.findall("Fractions"):
                    if _pp_text(frac_el, "Fraction") == "W":
                        win_time_hundredths = _pp_int(frac_el, "Time")
                        break

                # Past race context
                pp_track_code = _pp_text(pp_el, "Track", "TrackID", default="")
                pp_race_date_raw = _pp_text(pp_el, "RaceDate", default="")
                # Normalize date: '2022-05-28+00:00' → '2022-05-28'
                pp_race_date = pp_race_date_raw[:10] if pp_race_date_raw else ""
                pp_race_number = _pp_int(pp_el, "RaceNumber")
                pp_race_type = _pp_text(pp_el, "RaceType", "RaceType", default="")
                pp_surface = _pp_text(pp_el, "Course", "CourseType", "Value", default="")
                pp_distance = _pp_text(pp_el, "Distance", "PublishedValue", default="")
                pp_track_condition = _pp_text(pp_el, "TrackCondition", "Value", default="")
                field_size = _pp_int(pp_el, "NumberOfStarters")

                records.append({
                    "horse_name": horse_name,
                    "horse_name_key": horse_name_key,
                    "registration_number": reg_num,
                    "card_date": card_date,
                    "card_track_code": card_track_code,
                    "card_race_number": race_number,
                    "card_post_time": post_time,
                    "card_distance": race_distance,
                    "card_surface": race_surface,
                    "card_race_type": race_type,
                    "card_purse": race_purse,
                    "card_breed": race_breed,
                    "trainer_first": trainer_first,
                    "trainer_last": trainer_last,
                    "jockey_first": jockey_first,
                    "jockey_last": jockey_last,
                    "pp_track_code": pp_track_code,
                    "pp_race_date": pp_race_date,
                    "pp_race_number": pp_race_number,
                    "pp_race_type": pp_race_type,
                    "pp_surface": pp_surface,
                    "pp_distance": pp_distance,
                    "pp_track_condition": pp_track_condition,
                    "speed_figure": speed_figure,
                    "pace_figure_1": pace_1,
                    "pace_figure_2": pace_2,
                    "pace_figure_3": pace_3,
                    "class_rating": class_rating,
                    "official_finish": official_finish,
                    "post_position": post_position,
                    "pp_jockey_first": pp_jockey_first,
                    "pp_jockey_last": pp_jockey_last,
                    "earnings_usd": earnings_usd,
                    "odds_decimal": odds_decimal,
                    "win_time_hundredths": win_time_hundredths,
                    "field_size": field_size,
                    "short_comment": short_comment,
                    "long_comment": long_comment,
                })

    return records
