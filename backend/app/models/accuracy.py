"""
Models for Secretariat's prediction tracking, daily accuracy reports,
and rolling calibration data.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RacePrediction(Base):
    """One row per race × analysis_mode × user_id — Secretariat's pre-race top-4 call.
    user_id=NULL means the nightly global auto-prediction.
    """
    __tablename__ = "race_predictions"
    __table_args__ = (
        UniqueConstraint("race_id", "analysis_mode", name="uq_race_prediction"),
        UniqueConstraint("race_id", "analysis_mode", "user_id", name="uq_prediction_race_mode_user"),
        Index("ix_race_predictions_race_date", "race_date"),
        Index("ix_race_predictions_race_id", "race_id"),
        Index("ix_race_predictions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[str] = mapped_column(String(100), nullable=False)
    race_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    track_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    race_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    race_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    surface: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 'na' or 'int'
    analysis_mode: Mapped[str] = mapped_column(String(20), default="balanced")

    # Predicted finish (names as Secretariat returned them)
    predicted_first: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    predicted_second: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    predicted_third: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    predicted_fourth: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    predicted_first_num: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Actual results (populated by nightly_accuracy.py)
    actual_first: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    actual_second: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    actual_third: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    result_fetched: Mapped[bool] = mapped_column(Boolean, default=False)

    # Outcome flags
    top_pick_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    in_the_money: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Post-race reflection — populated by nightly_reflect.py
    reflection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyAccuracyReport(Base):
    """Aggregated daily performance summary — one row per calendar date."""
    __tablename__ = "daily_accuracy_reports"
    __table_args__ = (
        Index("ix_daily_accuracy_report_date", "report_date", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_races: Mapped[int] = mapped_column(Integer, default=0)
    races_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    top_pick_wins: Mapped[int] = mapped_column(Integer, default=0)
    in_the_money: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    itm_rate: Mapped[float] = mapped_column(Float, default=0.0)
    best_call: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    worst_miss: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    by_mode: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    by_track: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    by_race_type: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class SecretariatCalibration(Base):
    """
    Single-row rolling calibration state — always UPDATE id=1, never INSERT a second row.
    Populated nightly by nightly_recalibration.py and injected into every analysis prompt.
    """
    __tablename__ = "secretariat_calibration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    rolling_win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate_by_mode: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    win_rate_by_track: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    win_rate_by_type: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    win_rate_by_surface: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Lists of strings like "Maiden races (28% win rate, 18 races)"
    weak_spots: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    strong_spots: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Synthesized lessons from nightly_reflect.py — injected into every analysis prompt
    lessons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
