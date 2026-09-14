"""
Which lessons actually reach the pick prompt, and on what evidence.

The old rule was `cal.lessons[:5]` against a list ordered newest-first. That made
memory a five-slot recency window: a lesson written last night displaced one that
had been earning its place for a month, and the nightly curator carefully ranked
fourteen lessons of which nine were never read by anything. Secretariat noticed
before we did, and wrote it in its own digest — that it kept reading a lesson in
its notes and never applying it. It was right, literally.

Selection here is by measured record instead of recency, and the change ships
behind a per-race A/B so the question "did this help?" gets an answer from
results rather than from argument.
"""
import hashlib
import os

# How many lessons the evidence-ranked arm injects. Higher than the old 5 so a
# proven lesson is not evicted by a brand-new one, but still bounded — the block
# rides in every pick prompt, and an unbounded playbook is just noise.
LESSON_INJECT_LIMIT = int(os.getenv("LESSON_INJECT_LIMIT", "8"))
# The control arm reproduces the old behaviour exactly, so the A/B measures the
# change and nothing else.
LESSON_CONTROL_LIMIT = int(os.getenv("LESSON_CONTROL_LIMIT", "5"))
# Percentage of races routed to the evidence-ranked arm. 0 ends the experiment
# and sends every race to the old behaviour.
LESSON_AB_PERCENT = int(os.getenv("LESSON_AB_PERCENT", "50"))
# In the measured arm, each lesson is withheld from this share of races, decided
# per race AND per lesson. Until this existed every measured race carried the
# same top lessons, so "races that carried lesson X" was just "the measured arm":
# each lesson's verdict was the arm difference counted again under its name,
# which is why two different lessons showed identical records. An independent
# coin flip per lesson gives every lesson its own control group. 0 turns it off.
LESSON_HOLDOUT_PERCENT = int(os.getenv("LESSON_HOLDOUT_PERCENT", "50"))
# A PROVEN lesson has already beaten its control, so it is withheld far less
# often: enough to keep checking it still works, not so much that most races
# lose it.
LESSON_PROVEN_HOLDOUT_PERCENT = int(os.getenv("LESSON_PROVEN_HOLDOUT_PERCENT", "10"))
# How many top-ranked lessons are under test at once. Twice the prompt limit, so
# with half of them withheld a prompt still carries about LESSON_INJECT_LIMIT,
# and each lesson under test is in roughly half the measured races. Testing every
# active lesson instead would thin that exposure as the table grows and slow
# every verdict.
LESSON_ELIGIBLE_LIMIT = int(os.getenv("LESSON_ELIGIBLE_LIMIT", str(2 * LESSON_INJECT_LIMIT)))

ARM_MEASURED = "measured"
ARM_RECENCY = "recency"


def lesson_arm_for_race(race_id: str) -> str:
    """Which lesson-selection arm this race uses. Deterministic per race_id.

    Same md5 approach as the model A/B, and for the same reasons: a re-run or the
    --only-missing second pass must never flip a race mid-experiment, and the
    split must be independent of track, date and field size so neither arm gets
    the easier races.

    A different salt than the model A/B, so the two experiments stay independent
    rather than assigning identical races to both challengers.
    """
    if LESSON_AB_PERCENT <= 0 or not race_id:
        return ARM_RECENCY
    digest = hashlib.md5(f"lessons:{race_id}".encode()).hexdigest()[:8]
    return ARM_MEASURED if int(digest, 16) % 100 < LESSON_AB_PERCENT else ARM_RECENCY


def _sort_key_measured(lesson):
    """PROVEN first by size of lift, then everything unproven by recency.

    A lesson with a measured positive lift outranks one that merely arrived last
    night. Among equals, newer wins — recency is the tiebreak, not the rule.
    """
    verdict_rank = {"PROVEN": 0}.get(getattr(lesson, "verdict", "PENDING"), 1)
    lift = getattr(lesson, "lift", None)
    created = getattr(lesson, "created_at", None)
    return (
        verdict_rank,
        -(lift if lift is not None else 0.0),
        -(created.timestamp() if created else 0.0),
    )


def select_lessons(lessons: list, arm: str = ARM_MEASURED, limit: int | None = None) -> list:
    """The lessons to inject, in priority order.

    Pure over its input so it can be tested without a database.

    The measured arm drops anything scored FAILING — a lesson whose own scope got
    worse after it was applied is worse than no lesson. It also guarantees one
    CONTINUE lesson a slot when one exists: ranked purely by recency the playbook
    filled with CHANGE lessons, so Secretariat was told what to stop doing and
    never what to keep doing.
    """
    active = [l for l in lessons if getattr(l, "status", "active") == "active"]

    if arm == ARM_RECENCY:
        # Old behaviour, verbatim: newest first, no filtering on evidence.
        by_recency = sorted(
            active,
            key=lambda l: -(getattr(l, "created_at", None).timestamp()
                            if getattr(l, "created_at", None) else 0.0),
        )
        return by_recency[: (limit or LESSON_CONTROL_LIMIT)]

    limit = limit or LESSON_INJECT_LIMIT
    eligible = [l for l in active if getattr(l, "verdict", "PENDING") != "FAILING"]
    ranked = sorted(eligible, key=_sort_key_measured)
    chosen = ranked[:limit]

    if limit > 0 and not any(getattr(l, "lesson_type", "change") == "continue" for l in chosen):
        best_continue = next(
            (l for l in ranked if getattr(l, "lesson_type", "change") == "continue"), None
        )
        if best_continue is not None:
            chosen = chosen[: limit - 1] + [best_continue]

    return chosen


def lesson_withheld(race_id: str, lesson) -> bool:
    """Whether this race's prompt withholds this lesson. Deterministic per
    (race_id, lesson id), so the prompt and the stored provenance agree and a
    second predict pass never flips it.

    Its own salt, so being withheld is independent of the arm split, the model
    split and every other lesson's coin flip.
    """
    pct = (LESSON_PROVEN_HOLDOUT_PERCENT if getattr(lesson, "verdict", None) == "PROVEN"
           else LESSON_HOLDOUT_PERCENT)
    if pct <= 0 or not race_id:
        return False
    digest = hashlib.md5(f"holdout:{race_id}:{getattr(lesson, 'id', None)}".encode()).hexdigest()[:8]
    return int(digest, 16) % 100 < pct


def assign_lessons(lessons: list, race_id: str, arm: str = ARM_MEASURED,
                   limit: int | None = None) -> tuple[list, list]:
    """(carried, withheld) for one race's prompt.

    The recency arm is the old behaviour verbatim and withholds nothing.

    In the measured arm the top LESSON_ELIGIBLE_LIMIT lessons (active, not
    FAILING, in rank order) each get their own coin flip. Survivors fill the
    prompt in rank order up to `limit`; survivors past the limit are withheld
    too. That is still random with respect to the race, because which lessons
    survive depends only on the hashes. A surviving CONTINUE lesson keeps its
    guaranteed slot, but a CONTINUE lesson the coin flip withheld stays withheld,
    or it would never get a control group.
    """
    if arm == ARM_RECENCY or LESSON_HOLDOUT_PERCENT <= 0:
        return select_lessons(lessons, arm=arm, limit=limit), []

    limit = limit or LESSON_INJECT_LIMIT
    active = [l for l in lessons if getattr(l, "status", "active") == "active"]
    ranked = sorted(
        (l for l in active if getattr(l, "verdict", "PENDING") != "FAILING"),
        key=_sort_key_measured,
    )[:LESSON_ELIGIBLE_LIMIT]
    survivors = [l for l in ranked if not lesson_withheld(race_id, l)]
    carried = survivors[:limit]

    if limit > 0 and not any(getattr(l, "lesson_type", "change") == "continue" for l in carried):
        spare = next((l for l in survivors[limit:]
                      if getattr(l, "lesson_type", "change") == "continue"), None)
        if spare is not None:
            carried = carried[: limit - 1] + [spare]

    carried_ids = {id(l) for l in carried}
    withheld = [l for l in ranked if id(l) not in carried_ids]
    return carried, withheld


def render_lessons_block(lessons: list) -> str:
    """The prompt section. Empty when there is nothing worth injecting."""
    if not lessons:
        return ""
    lines = ["LESSONS FROM RECENT RACES (apply these now):"]
    for lesson in lessons:
        text = getattr(lesson, "text", str(lesson))
        # A proven lesson is labelled so, with its own numbers. "Back this
        # harder, it is measurably working" is a different instruction than
        # "here is something I wrote down once".
        if getattr(lesson, "verdict", None) == "PROVEN" and getattr(lesson, "lift", None):
            lines.append(f"  - [PROVEN: +{lesson.lift:.1f} pts in its own races] {text}")
        else:
            lines.append(f"  - {text}")
    return "\n".join(lines)


async def load_active_lessons() -> list:
    """Active lessons from the database. Empty list on any failure —
    the playbook is an enhancement and must never block producing a pick."""
    try:
        from sqlalchemy import select

        from app.core.database import _AsyncSessionLocal
        from app.models.lesson import SecretariatLesson

        if not _AsyncSessionLocal:
            return []
        async with _AsyncSessionLocal() as db:
            rows = await db.execute(
                select(SecretariatLesson).where(SecretariatLesson.status == "active")
            )
            return list(rows.scalars().all())
    except Exception:
        return []


# ── Per-race selection ───────────────────────────────────────────────────────
# The active set is read once and reused for a short window. A nightly run makes
# hundreds of calls in a few minutes and the playbook only changes once a day, so
# re-querying per race would be pure overhead. The window is short enough that a
# reflect run mid-slate is picked up on the next refresh.
_CACHE_TTL_SECONDS = 300
_cached_lessons: list | None = None
_cached_at: float = 0.0


# When frozen, the snapshot never refreshes for the life of the process. A
# nightly run builds its prompts, submits a batch, and polls for up to 45
# minutes before writing rows — and score_lessons runs on its own schedule in
# between, rewriting the very verdict/lift/status fields the ranking reads. With
# a plain TTL the write-time lookup was guaranteed to be a different query than
# the prompt-time one, so races got credited to lessons they never carried.
_frozen = False


def freeze_lessons(frozen: bool = True) -> None:
    """Pin the active set for this process. Batch jobs must call this at start."""
    global _frozen
    _frozen = frozen


def _invalidate_cache() -> None:
    global _cached_lessons, _cached_at
    _cached_lessons, _cached_at = None, 0.0


async def _active_lessons_cached() -> list:
    import time

    global _cached_lessons, _cached_at
    now = time.monotonic()
    if _cached_lessons is not None and _frozen:
        return _cached_lessons
    if _cached_lessons is None or (now - _cached_at) > _CACHE_TTL_SECONDS:
        _cached_lessons = await load_active_lessons()
        _cached_at = now
    return _cached_lessons


async def lesson_assignment_for_race(race_id: str) -> tuple[str, list, list]:
    """The arm this race is in, the lessons its prompt carries, and the eligible
    lessons it withheld.

    One function so the prompt and the stored provenance can never disagree:
    whatever this returns is both what the model was told and what we record
    having told it. A lesson's measured record is only worth anything if the
    "was it applied?" column is exactly right.
    """
    arm = lesson_arm_for_race(race_id)
    carried, withheld = assign_lessons(await _active_lessons_cached(), race_id, arm=arm)
    return arm, carried, withheld


async def lessons_for_race(race_id: str) -> tuple[str, list]:
    """The arm this race is in, and the lessons its prompt receives."""
    arm, carried, _withheld = await lesson_assignment_for_race(race_id)
    return arm, carried
