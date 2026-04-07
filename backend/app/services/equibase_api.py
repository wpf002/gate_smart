"""
Equibase / TrackMaster result chart parser.
Parses TrackMaster tchSchema.xsd XML files (file naming: {TRK}{yyyymmdd}tch.xml).
Provides speed figures and race history for US horses.
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
