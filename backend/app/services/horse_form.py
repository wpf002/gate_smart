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


def lines_for_field(field_size: int) -> int:
    """How many past starts to show per horse, scaled to field size.

    Form is the most valuable thing in the prompt, so it is trimmed last and
    never to zero — but a 14-runner field at 4 lines each is ~56 lines, so
    depth is traded for breadth as fields grow.
    """
    if field_size <= 8:
        return MAX_LINES_PER_HORSE
    if field_size <= 12:
        return 3
    return 2


def horse_key(name: str) -> str:
    """Join key for a horse name — lowercase, punctuation stripped.

    Results and entries disagree on punctuation ("O'Brien's Lad" vs "OBriens
    Lad"), so the key has to survive that or a horse's own history won't match.
    """
    cleaned = re.sub(r"['’.]", "", (name or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", cleaned)).strip()[:160]


# Comma, or "and" fenced by 2+ spaces. A single-spaced "and" is part of a name.
_ALSO_RAN_SPLIT = r",|\s{2,}and\s{2,}"


def parse_also_ran(also_ran) -> list[str]:
    """Names of horses that ran but finished outside the charted top 3.

    The feed is inconsistent: some meets return a list of names, others a single
    string joining them. Iterating a string yields characters, so this must
    never assume a list — doing so once wrote 517k single-letter "horses" into
    the archive and inflated field_size on every real runner in those races.

    The string form is comma-separated with the final name joined by a
    MULTI-SPACE "and":
        'Me and Chili, Ferdan, King Social  and   Forever Lasting'
    Splitting on any " and " tears real names apart — "Me and Chili" is one
    horse. Only a run of 2+ spaces around "and" is a separator.
    """
    if not also_ran:
        return []
    if isinstance(also_ran, str):
        parts = re.split(_ALSO_RAN_SPLIT, also_ran)
    elif isinstance(also_ran, (list, tuple)):
        parts = []
        for item in also_ran:
            if isinstance(item, str):
                parts.extend(re.split(_ALSO_RAN_SPLIT, item))
            elif isinstance(item, dict):
                parts.append(item.get("horse_name") or item.get("horse") or "")
    else:
        return []
    return [p.strip() for p in parts if p and p.strip()]


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
    also_ran = parse_also_ran(result.get("also_ran"))
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


async def record_race_form(result: dict, race_date=None, raise_on_error: bool = False) -> int:
    """Persist form lines for one settled race. Idempotent.

    Retries transient database failures (dropped pooled connection, DNS blip on
    a long backfill) before giving up. With `raise_on_error`, a persistent
    failure propagates so a batch caller can retry the whole date rather than
    silently banking a partial result — a partially-written date still looks
    "covered" to the backfill, which would make the loss permanent.

    During live settlement the default (swallow) is right: form is an
    enhancement and must never break settling a race.
    """
    import asyncio

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.core import database as _db
    from app.models.form import HorseFormLine

    rows = extract_form_rows(result, race_date)
    if not rows:
        return 0

    last_err = None
    for attempt in range(3):
        try:
            async with _db._AsyncSessionLocal() as db:
                stmt = pg_insert(HorseFormLine).values(rows)
                stmt = stmt.on_conflict_do_nothing(constraint="uq_form_horse_race")
                await db.execute(stmt)
                await db.commit()
            return len(rows)
        except Exception as e:
            last_err = e
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))

    log.warning(f"[horse_form] record failed for {result.get('race_id')}: {last_err}")
    if raise_on_error:
        raise RuntimeError(f"{result.get('race_id')}: {last_err}")
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
