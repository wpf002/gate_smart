"""
Pick contests: users call the winner of a race before post time and score points.

No money moves, nothing is wagered, and there are no prizes — prizes would pull a
free contest into sweepstakes law. It exists to teach handicapping and to give
people a reason to come back.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContestPick(Base):
    __tablename__ = "contest_picks"
    __table_args__ = (
        # One call per user per race. Changing it before post replaces the row.
        UniqueConstraint("user_id", "race_id", name="uq_contest_pick_user_race"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    race_id: Mapped[str] = mapped_column(String(100), index=True)
    race_date: Mapped[date] = mapped_column(Date, index=True)
    horse_name: Mapped[str] = mapped_column(String(160))
    horse_key: Mapped[str] = mapped_column(String(160))
    program_number: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # win | place | show | exacta | trifecta — see services.contest.BET_TYPES.
    # NULL on rows made before bet types existed; those are win bets.
    bet_type: Mapped[Optional[str]] = mapped_column(String(12), nullable=True, default="win")
    # The full selection, in order: [{"name", "key", "number"}, ...]. One entry
    # for a straight bet, two for an exacta, three for a trifecta. horse_name /
    # horse_key / program_number above always mirror selection 1, so every query
    # and UI written before exotics keeps working unchanged.
    selections: Mapped[Optional[list]] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Filled in once the official result is in.
    settled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    winner_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    secretariat_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    beat_secretariat: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    # What $2 on this bet returned at the official payoff, stake included: 0.0
    # is a settled loss, NULL is a pool the chart never priced. Nothing is
    # wagered — this is a scorekeeping figure, the same one the Report Card
    # publishes for Secretariat.
    payoff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # The official finish, top four: [{"position", "name", "number"}, ...].
    # Without it a graded pick could only say "+0" — a trifecta that had the
    # winner in the wrong order looked identical to one that had nothing.
    finish: Mapped[Optional[list]] = mapped_column(JSON(none_as_null=True), nullable=True)
