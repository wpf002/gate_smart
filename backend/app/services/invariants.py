"""
Assertions about production data that must hold every day.

The regressions that hurt most were not crashes. Production ran the losing
model for three days, an analysis cache was warmed under a key nobody read for
weeks, and 517k junk rows entered the form archive — none of it raised, none of
it failed a health check, and all of it was found by luck or by audit.

A health check answers "is it up". These answer "is it doing the right thing",
which is the question that kept going unasked.

Each check returns None when healthy or a short human sentence when violated.
They are deliberately conservative: racing data is legitimately irregular —
light Monday cards, tracks going dark, feeds dropping meets — and a check that
cries wolf gets muted, which is worse than no check at all.
"""
import logging
import os

log = logging.getLogger(__name__)

# A slate this small is a real racing day (a light Monday), not a failure.
_MIN_PLAUSIBLE_SLATE = 20


async def _fetch(db, sql: str, *args):
    from sqlalchemy import text as T
    return (await db.execute(T(sql), *args)).all()


async def check_pick_model_mix(db) -> str | None:
    """Every nightly pick should use the model we think we are running.

    This is the check that would have caught production silently running Haiku —
    the arm measured 8.8 points worse — for three days after an environment
    variable was reset outside the repo.
    """
    from app.services.secretariat import (
        PICK_MODEL_AB_PERCENT, PICK_MODEL_CHALLENGER, PICK_MODEL_DEFAULT,
    )
    rows = await _fetch(db, """
        SELECT pick_model, COUNT(*) n FROM race_predictions
        WHERE analysis_mode = 'auto_daily' AND user_id IS NULL
          AND lock_source = 'nightly' AND race_date = CURRENT_DATE - 1
        GROUP BY 1
    """)
    counts = {r[0]: r[1] for r in rows if r[0]}
    total = sum(counts.values())
    if total < _MIN_PLAUSIBLE_SLATE:
        return None

    unexpected = {m: n for m, n in counts.items()
                  if m not in (PICK_MODEL_DEFAULT, PICK_MODEL_CHALLENGER)}
    if unexpected:
        return f"picks used unrecognised model(s): {unexpected}"

    challenger = counts.get(PICK_MODEL_CHALLENGER, 0)
    share = 100.0 * challenger / total
    # Wide tolerance: the split is a hash over race ids, so a small slate swings.
    if abs(share - PICK_MODEL_AB_PERCENT) > 15:
        return (f"model split is {share:.0f}% {PICK_MODEL_CHALLENGER} over {total} picks, "
                f"but PICK_MODEL_AB_PERCENT is {PICK_MODEL_AB_PERCENT} — "
                f"configuration and behaviour disagree")
    return None


async def check_provenance_shape(db) -> str | None:
    """lesson_ids must be a real array or SQL NULL — never a JSON null.

    A JSON null passes `IS NOT NULL`, decodes to None, and gets counted as
    control evidence for lessons the race never carried.
    """
    rows = await _fetch(db, """
        SELECT COUNT(*) FROM race_predictions
        WHERE analysis_mode = 'auto_daily' AND user_id IS NULL
          AND race_date >= CURRENT_DATE - 2
          AND lesson_ids IS NOT NULL AND jsonb_typeof(lesson_ids) <> 'array'
    """)
    bad = rows[0][0] if rows else 0
    if bad:
        return f"{bad} prediction rows hold a non-array lesson_ids (jsonb null leak)"
    return None


async def check_form_archive_integrity(db) -> str | None:
    """The signature of the also_ran character-split bug, on the live path.

    It once wrote 517k single-letter "horses" and inflated field_size on every
    real runner in those races. The backfill script gained a gate afterwards;
    the nightly path never had one.
    """
    rows = await _fetch(db, """
        SELECT
          COUNT(*) FILTER (WHERE LENGTH(horse_key) < 2) junk,
          COUNT(*) FILTER (WHERE field_size > 30) huge
        FROM horse_form_lines WHERE race_date >= CURRENT_DATE - 2
    """)
    if not rows:
        return None
    junk, huge = rows[0]
    if junk or huge:
        return (f"form archive: {junk} single-character horse names, "
                f"{huge} rows with field_size > 30 in the last 2 days")
    return None


async def check_grading_self_consistency(db) -> str | None:
    """A winning pick must also be in the money. If those disagree, the
    scoring that every reported percentage rests on is broken."""
    rows = await _fetch(db, """
        SELECT COUNT(*) FROM race_predictions
        WHERE analysis_mode = 'auto_daily' AND user_id IS NULL
          AND result_fetched AND race_date >= CURRENT_DATE - 2
          AND top_pick_correct AND NOT in_the_money
    """)
    bad = rows[0][0] if rows else 0
    if bad:
        return f"{bad} races graded as a winning pick but not in the money"
    return None


async def check_slate_coverage(db) -> str | None:
    """The most recently REPORTED day should have been fully graded.

    Anchored to the latest accuracy report rather than to "yesterday". Yesterday
    is still running until settlement at 10:00 UTC, so a calendar-based check
    fires every night between midnight and mid-morning — and an alert that goes
    off on healthy days is one the owner learns to ignore.
    """
    rows = await _fetch(db, """
        SELECT COUNT(*) total, COUNT(*) FILTER (WHERE result_fetched) settled
        FROM race_predictions
        WHERE analysis_mode = 'auto_daily' AND user_id IS NULL
          AND race_date = (SELECT MAX(report_date) FROM daily_accuracy_reports)
    """)
    if not rows:
        return None
    total, settled = rows[0]
    if total < _MIN_PLAUSIBLE_SLATE:
        return None
    if settled / total < 0.9:
        return (f"only {settled}/{total} of yesterday's picks are settled — "
                f"every rate reported today is computed over a subset")
    return None


async def check_cost_per_pick(db) -> str | None:
    """A cost blowout is a behaviour change we would otherwise learn about from
    a bill: caching broken, a retry loop, or a model swapped underneath us."""
    ceiling = float(os.getenv("COST_PER_PICK_CEILING", "0.12"))
    rows = await _fetch(db, """
        SELECT COALESCE(SUM(est_cost_usd), 0) usd, COUNT(*) n
        FROM llm_call_log
        WHERE endpoint LIKE 'analyze_race%' AND call_date = CURRENT_DATE - 1
    """)
    if not rows or not rows[0][1]:
        return None
    usd, n = float(rows[0][0]), rows[0][1]
    per = usd / n
    if per > ceiling:
        return f"analysis cost ${per:.4f}/pick over {n} calls, above the ${ceiling:.2f} ceiling"
    return None


CHECKS = (
    ("pick model mix", check_pick_model_mix),
    ("lesson provenance shape", check_provenance_shape),
    ("form archive integrity", check_form_archive_integrity),
    ("grading self-consistency", check_grading_self_consistency),
    ("slate coverage", check_slate_coverage),
    ("cost per pick", check_cost_per_pick),
)


async def run_invariants() -> list[tuple[str, str]]:
    """Run every check. Returns [(label, violation)] — empty means healthy.

    A check that raises is reported as a violation rather than swallowed: a
    check that silently stops checking is the failure mode this file exists to
    prevent.
    """
    from app.core.database import _AsyncSessionLocal

    if not _AsyncSessionLocal:
        return []
    violations: list[tuple[str, str]] = []
    async with _AsyncSessionLocal() as db:
        for label, check in CHECKS:
            try:
                result = await check(db)
            except Exception as e:
                violations.append((label, f"check itself failed: {type(e).__name__}: {e}"))
                continue
            if result:
                violations.append((label, result))
    return violations
