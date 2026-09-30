"""
Equibase speed figures, pace figures and trip comments, from our own archive.

The system prompt has always told Secretariat it gets "no speed or pace
figures ... no finishing positions below 3rd ... no trip notes". That was true
of the live feed and of horse_form_lines, which keeps top-three finishes only.
It was never true of horse_past_performances, which has been sitting in the
database unused: 274,000 runs in 2022 and 348,000 in 2023, carrying a speed
figure, three pace calls, a class rating, the actual finishing position however
far back it was, the closing odds, and a chart caller's note on the trip.

For a card of 725 runners, 255 of them have lines here — a third of the field
handicapped with figures rather than finishing positions alone.

The one hard limit, stated in the block itself: the archive ends 28 Dec 2023.
Every figure is two or three years old, so it describes a horse's established
level, not its current form. Recent form still comes from horse_form_lines.
"""
import asyncio

from app.core import database as _db

# Enough to establish a level without burying the recent form that follows it.
MAX_LINES_PER_HORSE = 4
ARCHIVE_ENDS = "2023-12-28"

_SURFACE = {"D": "dirt", "T": "turf", "E": "turf", "A": "all-weather", "I": "inner turf"}
_GOING = {"FT": "fast", "MY": "muddy", "SY": "sloppy", "GD": "good", "YL": "yielding",
          "SF": "soft", "FM": "firm", "WF": "wet-fast", "HY": "heavy", "SL": "slow"}


def _pace(row) -> str:
    """Pace calls, collapsed when the feed repeats one figure across all three."""
    calls = [row.get("pace_figure_1"), row.get("pace_figure_2"), row.get("pace_figure_3")]
    calls = [c for c in calls if c is not None]
    if not calls:
        return ""
    if len(set(calls)) == 1:
        return f" pace {calls[0]}"
    return " pace " + "/".join(str(c) for c in calls)


def _line(row) -> str:
    surface = _SURFACE.get((row.get("pp_surface") or "").upper(), row.get("pp_surface") or "")
    going = _GOING.get((row.get("pp_track_condition") or "").upper(), "")
    finish = row.get("official_finish")
    field = row.get("field_size")
    pos = f"{finish}/{field}" if finish and field else (str(finish) if finish else "?")
    bits = [
        f"{row.get('pp_race_date')} {row.get('pp_track_code')}",
        f"{row.get('pp_distance')} {surface}".strip(),
    ]
    if going:
        bits.append(going)
    bits.append(f"fin {pos}")
    if row.get("speed_figure") is not None:
        bits.append(f"spd {row['speed_figure']}")
    pace = _pace(row)
    if pace:
        bits.append(pace.strip())
    if row.get("class_rating") is not None:
        bits.append(f"cls {row['class_rating']}")
    if row.get("odds_decimal"):
        bits.append(f"{float(row['odds_decimal']):.1f}-1")
    line = ", ".join(bits)
    note = (row.get("long_comment") or row.get("short_comment") or "").strip()
    return f"{line} — {note}" if note else line


async def get_chart_figures(runners: list) -> dict[str, list[str]]:
    """The most recent archived lines per runner, keyed by horse name."""
    names = [(r.get("horse_name") or "").strip() for r in runners or []
             if not r.get("scratched") and (r.get("horse_name") or "").strip()]
    if not names or not _db._AsyncSessionLocal:
        return {}
    from sqlalchemy import text as _text

    sql = _text("""
        SELECT horse_name, pp_race_date, pp_track_code, pp_distance, pp_surface,
               pp_track_condition, official_finish, field_size, speed_figure,
               pace_figure_1, pace_figure_2, pace_figure_3, class_rating,
               odds_decimal, short_comment, long_comment
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                       PARTITION BY lower(horse_name) ORDER BY pp_race_date DESC
                   ) AS rn
            FROM horse_past_performances
            WHERE lower(horse_name) = ANY(:names)
        ) ranked
        WHERE rn <= :per_horse
        ORDER BY horse_name, pp_race_date DESC
    """)
    async with _db._AsyncSessionLocal() as db:
        rows = (await db.execute(
            sql, {"names": [n.lower() for n in names], "per_horse": MAX_LINES_PER_HORSE}
        )).mappings().all()

    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(row["horse_name"], []).append(_line(row))
    return out


async def get_figures_context(runners: list) -> str:
    """The block, ready for a prompt. Never raises."""
    try:
        figures = await get_chart_figures(runners)
        if not figures:
            return ""
        # The archive capitalises differently from the feed — "Aaron'S Spirit"
        # against "Aaron's Spirit" — so match on the lowercased name or every
        # program number comes out as "?".
        by_name = {(r.get("horse_name") or "").strip().lower(): r for r in runners or []}
        lines = []
        for name, entries in figures.items():
            num = (by_name.get(name.strip().lower()) or {}).get("number", "?")
            lines.append(f"#{num} {name}:")
            lines.extend(f"    {e}" for e in entries)
        return (
            "\n\nCHART FIGURES AND TRIP NOTES (our Equibase archive, ends "
            f"{ARCHIVE_ENDS}):\n" + "\n".join(lines)
            + "\n- spd is the Equibase speed figure, pace the running-line calls, cls the "
              "class rating. Higher is better on all three.\n"
            "- fin is the ACTUAL finishing position out of the field, however far back — "
            "the only place you get beaten finishes, since the recent archive keeps the "
            "top three.\n"
            "- The note is the chart caller's account of the trip. A horse that was "
            "blocked, wide or bumped ran better than its position.\n"
            f"- Nothing here is later than {ARCHIVE_ENDS}. Treat these as the horse's "
            "established level and its trip history, not its current form — recent form "
            "is in the lines above. Say the year when you cite one."
        )
    except Exception as e:  # noqa: BLE001
        print(f"[chart_figures] unavailable: {type(e).__name__}: {e}")
        return ""
