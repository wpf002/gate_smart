"""
Secretariat's playbook, as data rather than prose.

Lessons used to live as a JSON list of sentences on the calibration row. Nothing
recorded when a lesson was born, which races it governed, or whether it ever
helped — so the nightly curator judged them on how they read, and the playbook
drifted on narrative instead of evidence. Fourteen accumulated while the win
rate sat flat for nineteen weeks.

One row per lesson, carrying its scope, its birth date, and its measured record.
That is what lets a lesson be retired for failing rather than for sounding stale.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SecretariatLesson(Base):
    """A single lesson, its scope, and how it has actually performed."""

    __tablename__ = "secretariat_lessons"
    __table_args__ = (
        # The same sentence must never be stored twice, or it would be measured
        # twice and double-count toward the injected set.
        UniqueConstraint("text_hash", name="uq_lesson_text_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # md5 of the text — Postgres cannot put a plain unique index on unbounded TEXT.
    text_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'change' (a correction), 'continue' (a read that worked), 'watch'.
    lesson_type: Mapped[str] = mapped_column(String(20), default="change")

    # Which races this lesson governs; see lesson_scope.parse_scope.
    scope: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 'active' — eligible for injection. 'retired' — measured as harmful, or
    # superseded. Retired lessons are kept, never deleted: the record of what
    # failed is the most useful thing in here.
    status: Mapped[str] = mapped_column(String(20), default="active")
    retire_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # When this lesson first reached the pick prompt. Evidence only counts from
    # here — races before it could not have been influenced by it.
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Measured record, refreshed by scripts/score_lessons.py ──────────────
    # In-scope races since activation.
    scope_races: Mapped[int] = mapped_column(Integer, default=0)
    scope_wins: Mapped[int] = mapped_column(Integer, default=0)
    # The same scope over the 21 days before activation — what performance looked
    # like without this lesson.
    baseline_races: Mapped[int] = mapped_column(Integer, default=0)
    baseline_wins: Mapped[int] = mapped_column(Integer, default=0)
    # scope win rate minus baseline win rate, in percentage points.
    lift: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Two-proportion p-value for that difference. Observational, not causal —
    # the A/B arm is what actually establishes cause.
    p_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 'PENDING' (too few races), 'PROVEN', 'UNPROVEN', 'FAILING'.
    verdict: Mapped[str] = mapped_column(String(20), default="PENDING")
    measured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # True once this lesson has been in the injected set at least once, so a
    # never-applied lesson is never scored as if it had been.
    was_injected: Mapped[bool] = mapped_column(Boolean, default=False)

    def win_rate(self) -> Optional[float]:
        return self.scope_wins / self.scope_races if self.scope_races else None

    def baseline_rate(self) -> Optional[float]:
        return self.baseline_wins / self.baseline_races if self.baseline_races else None
