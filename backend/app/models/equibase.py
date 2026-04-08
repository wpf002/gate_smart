"""
SQLAlchemy models for Equibase historical data.

Tables:
  horse_past_performances  — 2023 US PP data (SIMD XML)
  horse_result_charts      — 2023 US result chart data (TrackMaster TCH XML)

Both use horse_name_key as the primary lookup key (normalized lowercase slug).
"""
from typing import Optional

from sqlalchemy import (
    Date,
    Float,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HorsePastPerformance(Base):
    __tablename__ = "horse_past_performances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Horse identity
    horse_name_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    horse_name: Mapped[str] = mapped_column(String(120), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(40), default="")

    # Race card context (the card this PP file was filed for)
    card_date: Mapped[Optional[str]] = mapped_column(String(10))  # YYYY-MM-DD
    card_track_code: Mapped[str] = mapped_column(String(10), default="")
    card_race_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    card_post_time: Mapped[str] = mapped_column(String(20), default="")
    card_distance: Mapped[str] = mapped_column(String(40), default="")
    card_surface: Mapped[str] = mapped_column(String(20), default="")
    card_race_type: Mapped[str] = mapped_column(String(40), default="")
    card_purse: Mapped[float] = mapped_column(Float, default=0.0)
    card_breed: Mapped[str] = mapped_column(String(40), default="")

    # Current connections (as of card date)
    trainer_first: Mapped[str] = mapped_column(String(60), default="")
    trainer_last: Mapped[str] = mapped_column(String(60), default="")
    jockey_first: Mapped[str] = mapped_column(String(60), default="")
    jockey_last: Mapped[str] = mapped_column(String(60), default="")

    # Past race identity (the individual past performance being recorded)
    pp_track_code: Mapped[str] = mapped_column(String(10), default="", index=True)
    pp_race_date: Mapped[Optional[str]] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    pp_race_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    pp_race_type: Mapped[str] = mapped_column(String(40), default="")
    pp_surface: Mapped[str] = mapped_column(String(20), default="")
    pp_distance: Mapped[str] = mapped_column(String(40), default="")
    pp_track_condition: Mapped[str] = mapped_column(String(40), default="")

    # Figures (Beyer-comparable scale, stored as int after ÷10 from raw XML)
    speed_figure: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    pace_figure_1: Mapped[int] = mapped_column(SmallInteger, default=0)
    pace_figure_2: Mapped[int] = mapped_column(SmallInteger, default=0)
    pace_figure_3: Mapped[int] = mapped_column(SmallInteger, default=0)
    class_rating: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Result
    official_finish: Mapped[int] = mapped_column(SmallInteger, default=0)
    post_position: Mapped[int] = mapped_column(SmallInteger, default=0)
    field_size: Mapped[int] = mapped_column(SmallInteger, default=0)
    earnings_usd: Mapped[float] = mapped_column(Float, default=0.0)
    odds_decimal: Mapped[float] = mapped_column(Float, default=0.0)
    win_time_hundredths: Mapped[int] = mapped_column(Integer, default=0)

    # Jockey at time of the past race
    pp_jockey_first: Mapped[str] = mapped_column(String(60), default="")
    pp_jockey_last: Mapped[str] = mapped_column(String(60), default="")

    # Comments
    short_comment: Mapped[str] = mapped_column(String(200), default="")
    long_comment: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        # Unique constraint for dedup on re-ingest
        Index(
            "uq_pp_start",
            "horse_name_key", "pp_track_code", "pp_race_date", "pp_race_number",
            unique=True,
        ),
    )


class HorseResultChart(Base):
    __tablename__ = "horse_result_charts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Horse identity
    horse_name_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    horse_name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Race identity
    track_code: Mapped[str] = mapped_column(String(10), default="", index=True)
    track_name: Mapped[str] = mapped_column(String(80), default="")
    race_date: Mapped[Optional[str]] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    race_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    breed: Mapped[str] = mapped_column(String(40), default="")
    race_type: Mapped[str] = mapped_column(String(40), default="")
    purse: Mapped[int] = mapped_column(Integer, default=0)
    distance: Mapped[str] = mapped_column(String(40), default="")
    surface: Mapped[str] = mapped_column(String(20), default="")
    course_desc: Mapped[str] = mapped_column(String(40), default="")
    track_condition: Mapped[str] = mapped_column(String(40), default="")
    class_rating: Mapped[int] = mapped_column(SmallInteger, default=0)
    win_time: Mapped[int] = mapped_column(Integer, default=0)
    fraction_1: Mapped[int] = mapped_column(Integer, default=0)
    fraction_2: Mapped[int] = mapped_column(Integer, default=0)
    fraction_3: Mapped[int] = mapped_column(Integer, default=0)
    pace_final: Mapped[int] = mapped_column(Integer, default=0)
    footnotes: Mapped[str] = mapped_column(Text, default="")

    # Entry-level
    program_num: Mapped[str] = mapped_column(String(10), default="")
    post_pos: Mapped[int] = mapped_column(SmallInteger, default=0)
    official_finish: Mapped[int] = mapped_column(SmallInteger, default=0)
    speed_rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    weight: Mapped[int] = mapped_column(SmallInteger, default=0)
    age: Mapped[int] = mapped_column(SmallInteger, default=0)
    sex_code: Mapped[str] = mapped_column(String(4), default="")
    sex_desc: Mapped[str] = mapped_column(String(20), default="")
    meds: Mapped[str] = mapped_column(String(20), default="")
    equipment: Mapped[str] = mapped_column(String(40), default="")
    dollar_odds: Mapped[float] = mapped_column(Float, default=0.0)
    claim_price: Mapped[int] = mapped_column(Integer, default=0)
    jockey_first: Mapped[str] = mapped_column(String(60), default="")
    jockey_last: Mapped[str] = mapped_column(String(60), default="")
    jockey_key: Mapped[str] = mapped_column(String(80), default="")
    trainer_first: Mapped[str] = mapped_column(String(60), default="")
    trainer_last: Mapped[str] = mapped_column(String(60), default="")
    trainer_key: Mapped[str] = mapped_column(String(80), default="")
    owner: Mapped[str] = mapped_column(String(120), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    win_payoff: Mapped[float] = mapped_column(Float, default=0.0)
    place_payoff: Mapped[float] = mapped_column(Float, default=0.0)
    show_payoff: Mapped[float] = mapped_column(Float, default=0.0)
    points_of_call: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index(
            "uq_chart_entry",
            "horse_name_key", "track_code", "race_date", "race_number",
            unique=True,
        ),
    )
