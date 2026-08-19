"""
Horse form lines built from our own results ingestion.

The NA feed carries no past performances — every runner arrives with `form: ""` —
and the vendors that sell PPs (Equibase and its licensees) won't license to an
app. But we settle every NA race daily, so we can accumulate running lines
ourselves: one row per horse per race we've seen it run.

Coverage starts empty and compounds — horses run every few weeks, so this
becomes useful over a month or two and keeps improving. Unlike a vendor feed,
nobody can revoke it.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HorseFormLine(Base):
    __tablename__ = "horse_form_lines"
    __table_args__ = (
        # One line per horse per race; re-settling a day must not duplicate.
        UniqueConstraint("horse_key", "race_id", name="uq_form_horse_race"),
        Index("ix_form_horse_key_date", "horse_key", "race_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Normalized name — the feed gives no stable horse id in results, so the
    # name (punctuation-stripped, lowercased) is the join key.
    horse_key: Mapped[str] = mapped_column(String(160), nullable=False)
    horse_name: Mapped[str] = mapped_column(String(160), nullable=False)
    race_id: Mapped[str] = mapped_column(String(100), nullable=False)
    race_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    track: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    # NULL finish = ran but off the board (charts list only the top 3 by name,
    # the rest arrive via also_ran). Distinct from "didn't run".
    finish_pos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    field_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distance_f: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    surface: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    going: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    race_class: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Connections. Stored now because backfilling them later means re-pulling
    # every past result — and because trainer/jockey strike rate is a core
    # handicapping angle we can only ever compute from our own archive.
    jockey: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    trainer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    breed: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Winner's time and the race's own splits — lets us compare how fast a race
    # was run relative to others at the same track/distance.
    winning_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_payoff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
