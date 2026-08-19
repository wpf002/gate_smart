"""
Build and read horse form from our own results archive.

`record_race_form` turns one settled race result into form lines for every horse
that ran. `get_form_context` reads them back at analysis time so Secretariat
sees a runner's recent starts instead of nothing.
"""
import logging
import re

log = logging.getLogger(__name__)

# Keep the prompt affordable: recent starts matter, ancient ones don't.
MAX_LINES_PER_HORSE = 4


def horse_key(name: str) -> str:
    """Join key for a horse name — lowercase, punctuation stripped.

    Results and entries disagree on punctuation ("O'Brien's Lad" vs "OBriens
    Lad"), so the key has to survive that or a horse's own history won't match.
    """
    cleaned = re.sub(r"['’.]", "", (name or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", cleaned)).strip()[:160]


def extract_form_rows(result: dict, race_date=None) -> list[dict]:
    """One dict per horse that ran in this result.

    Charted runners (top 3) get their finish position; `also_ran` horses are
    recorded with finish_pos=None — we know they ran and were off the board,
    which is itself a real form line.
    """
    rows: list[dict] = []
    race_id = result.get("race_id")
    if not race_id:
        return rows

    charted = result.get("runners") or []
    also_ran = result.get("also_ran") or []
    field_size = len(charted) + len(also_ran)
    common = {
        "race_id": race_id,
        "race_date": race_date,
        "track": (result.get("track_name") or "")[:80],
        "field_size": field_size or None,
        "distance_f": result.get("distance_f"),
        "surface": (result.get("surface") or "")[:40],
        "going": (result.get("going") or "")[:40],
        "race_class": (result.get("race_class") or result.get("race_type") or "")[:120],
        "breed": (result.get("breed") or "")[:30],
        "winning_time": result.get("winning_time"),
    }

    seen = set()
    for r in charted:
        name = (r.get("horse_name") or r.get("horse") or "").strip()
        k = horse_key(name)
        if not k or k in seen:
            continue
        seen.add(k)
        try:
            pos = int(r.get("finish_position") or r.get("position") or 0) or None
        except (TypeError, ValueError):
            pos = None
        rows.append({**common, "horse_key": k, "horse_name": name[:160],
                     "finish_pos": pos, "win_payoff": r.get("win_payoff"),
                     "jockey": (r.get("jockey") or "")[:120] or None,
                     "trainer": (r.get("trainer") or "")[:120] or None})

    for name in also_ran:
        name = (name or "").strip()
        k = horse_key(name)
        if not k or k in seen:
            continue
        seen.add(k)
        rows.append({**common, "horse_key": k, "horse_name": name[:160],
                     "finish_pos": None, "win_payoff": None,
                     "jockey": None, "trainer": None})
    return rows


async def record_race_form(result: dict, race_date=None) -> int:
    """Persist form lines for one settled race. Idempotent."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.core import database as _db
    from app.models.form import HorseFormLine

    rows = extract_form_rows(result, race_date)
    if not rows:
        return 0
    try:
        async with _db._AsyncSessionLocal() as db:
            stmt = pg_insert(HorseFormLine).values(rows)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_form_horse_race")
            await db.execute(stmt)
            await db.commit()
        return len(rows)
    except Exception as e:
        log.warning(f"[horse_form] record failed for {result.get('race_id')}: {e}")
        return 0


def _format_line(f) -> str:
    """One compact past-performance line, e.g. '2/8 SAR 6.0f Dirt Fast CLM 10000'."""
    pos = f"{f.finish_pos}/{f.field_size}" if f.finish_pos and f.field_size else (
        f"{f.finish_pos}" if f.finish_pos else f"off/{f.field_size}" if f.field_size else "off"
    )
    bits = [
        f.race_date.isoformat() if f.race_date else "",
        pos,
        (f.track or "")[:18],
        f"{f.distance_f:g}f" if f.distance_f else "",
        (f.surface or "")[:10],
        (f.going or "")[:8],
        (f.race_class or "")[:26],
    ]
    return " ".join(b for b in bits if b)


async def get_form_context(runners: list[dict], limit: int = MAX_LINES_PER_HORSE) -> dict[str, list[str]]:
    """Recent form lines keyed by horse name, for the runners in one race.

    Returns {} on any failure — form is an enhancement, never a hard dependency
    of producing a pick.
    """
    from sqlalchemy import select

    from app.core import database as _db
    from app.models.form import HorseFormLine

    names = [(r.get("horse_name") or r.get("horse") or "") for r in runners or []]
    keys = {horse_key(n): n for n in names if horse_key(n)}
    if not keys:
        return {}
    try:
        async with _db._AsyncSessionLocal() as db:
            res = await db.execute(
                select(HorseFormLine)
                .where(HorseFormLine.horse_key.in_(list(keys.keys())))
                .order_by(HorseFormLine.race_date.desc().nulls_last())
            )
            lines = list(res.scalars().all())
    except Exception as e:
        log.info(f"[horse_form] lookup skipped: {e}")
        return {}

    out: dict[str, list[str]] = {}
    for f in lines:
        name = keys.get(f.horse_key)
        if not name:
            continue
        bucket = out.setdefault(name, [])
        if len(bucket) < limit:
            bucket.append(_format_line(f))
    return {k: v for k, v in out.items() if v}


def render_form_block(form: dict[str, list[str]]) -> str:
    """The prompt section. Empty string when we have no history yet."""
    if not form:
        return ""
    lines = [
        "\n\nPAST FORM (from our own result archive — most recent first).",
        "Format: date  finish/field  track  distance  surface  going  class.",
        '"off/N" means the horse ran and finished outside the top 3.',
        "Absence of lines means we have no record of that horse running, NOT that it is unraced:",
    ]
    for name, ls in form.items():
        lines.append(f"  {name}: " + " | ".join(ls))
    return "\n".join(lines)
