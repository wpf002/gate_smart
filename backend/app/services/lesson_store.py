"""
Writing lessons into the playbook.

The nightly reflect job produces a curated list of sentences. This turns that
list into tracked rows: each lesson gets a scope, a birth date, and from then on
a measured record.

One deliberate rule lives here. The curator is a language model judging lessons
on how they read, and it is the layer that let the playbook drift for nineteen
weeks. So when it drops a lesson that measurement has already shown to work, the
measurement wins and the lesson stays. Narrative can propose; only evidence
retires.
"""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)


def text_hash(text: str) -> str:
    return hashlib.md5((text or "").strip().encode()).hexdigest()


def lesson_type_of(text: str) -> str:
    """CONTINUE / CHANGE / WATCH prefix, as written by synthesise_lessons."""
    head = (text or "").strip().upper()
    for kind in ("CONTINUE", "CHANGE", "WATCH"):
        if head.startswith(kind):
            return kind.lower()
    return "change"


# A lesson needs this many in-scope races it was actually carried into before
# its record means anything. Mirrors score_lessons.MIN_TREATED.
MIN_TREATED_FOR_VERDICT = 80


def _protect_reason(row) -> str | None:
    """Why this lesson survives the curator dropping it, or None to retire it.

    The curator is an LLM judging lessons on how they read, and it minted ~8 new
    ones a night while dropping older ones — so 33 lessons were retired, every
    one of them "curated out", none on evidence, and nothing ever reached a
    verdict. Lessons were dying faster than they could be measured, which makes
    the whole measurement apparatus decorative.

    So narrative can no longer retire a lesson that is still earning its verdict.
    A lesson that was never injected gets no such protection — it has no claim to
    a fair hearing it never took, and without that exception the active list
    would grow without bound.
    """
    if getattr(row, "verdict", None) == "PROVEN":
        return "PROVEN"
    if getattr(row, "verdict", None) == "FAILING":
        return None  # measured harmful; let it go
    if getattr(row, "was_injected", False) and (row.scope_races or 0) < MIN_TREATED_FOR_VERDICT:
        return f"still gathering evidence ({row.scope_races or 0}/{MIN_TREATED_FOR_VERDICT} races)"
    return None


async def sync_lessons(texts: list[str]) -> dict:
    """Reconcile the playbook table with the curator's list.

    Returns a summary dict. Never raises — a reflect run must still finish if the
    playbook write fails.
    """
    from sqlalchemy import select

    from app.core.database import _AsyncSessionLocal
    from app.models.lesson import SecretariatLesson
    from app.services.lesson_scope import parse_scope

    summary = {"new": 0, "kept": 0, "retired": 0, "protected": 0}
    if not _AsyncSessionLocal:
        return summary

    now = datetime.now(timezone.utc)
    # Position in the curator's list is meaningful — it is newest-first, and the
    # control arm selects by recency. Seeding a whole list at one timestamp would
    # leave that ordering arbitrary, so positions are staggered to preserve it.
    ordered = [t for t in texts if t and str(t).strip()]
    wanted = {text_hash(t): t for t in ordered}
    birth = {text_hash(t): now - timedelta(seconds=i) for i, t in enumerate(ordered)}

    try:
        async with _AsyncSessionLocal() as db:
            existing = {
                row.text_hash: row
                for row in (await db.execute(select(SecretariatLesson))).scalars().all()
            }

            for h, text in wanted.items():
                row = existing.get(h)
                if row is None:
                    db.add(SecretariatLesson(
                        text=text,
                        text_hash=h,
                        lesson_type=lesson_type_of(text),
                        scope=parse_scope(text),
                        status="active",
                        created_at=birth[h],
                        # Evidence counts from the moment it can influence a pick.
                        activated_at=now,
                    ))
                    summary["new"] += 1
                else:
                    if row.status != "active":
                        # The curator brought a retired lesson back. Restart its
                        # record rather than blending two separate lifetimes.
                        row.status = "active"
                        row.activated_at = now
                        row.retired_at = None
                        row.retire_reason = None
                    summary["kept"] += 1

            for h, row in existing.items():
                if h in wanted or row.status != "active":
                    continue
                keep_reason = _protect_reason(row)
                if keep_reason:
                    summary["protected"] += 1
                    log.info(f"[lesson_store] kept lesson the curator dropped "
                             f"({keep_reason}): {row.text[:70]}")
                    continue
                row.status = "retired"
                row.retired_at = now
                row.retire_reason = "curated out of the active playbook"
                summary["retired"] += 1

            await db.commit()

        from app.services.lesson_memory import _invalidate_cache
        _invalidate_cache()
    except Exception as e:
        log.warning(f"[lesson_store] sync failed: {e}")

    return summary
