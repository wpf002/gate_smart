"""
Pick contests: users call the winner of a race before post time and score points.

No money moves, nothing is wagered, and there are no prizes — prizes would pull a
free contest into sweepstakes law. It exists to teach handicapping and to give
people a reason to come back.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Filled in once the official result is in.
    settled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    winner_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    secretariat_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    beat_secretariat: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
