"""
SQLAlchemy models for user accounts and Postgres-backed paper trading.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Betting profile (synced from frontend onboarding)
    bankroll: Mapped[float] = mapped_column(Float, default=500.0)
    risk_tolerance: Mapped[str] = mapped_column(String(20), default="medium")
    experience_level: Mapped[str] = mapped_column(String(20), default="beginner")
    region: Mapped[str] = mapped_column(String(20), default="usa")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    paper_bets: Mapped[list["PaperBet"]] = relationship(
        "PaperBet", back_populates="user", lazy="select"
    )


class PaperBet(Base):
    __tablename__ = "paper_bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Bet identity (matches existing Redis dict schema)
    bet_id: Mapped[str] = mapped_column(String(20), nullable=False)
    race_id: Mapped[str] = mapped_column(String(100), nullable=False)
    horse_id: Mapped[str] = mapped_column(String(100), nullable=False)
    horse_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bet_type: Mapped[str] = mapped_column(String(20), nullable=False)
    odds: Mapped[str] = mapped_column(String(20), default="")
    stake: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    returns: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    placed_at: Mapped[str] = mapped_column(String(40), default="")
    settled_at: Mapped[str] = mapped_column(String(40), default="")
    race_name: Mapped[str] = mapped_column(String(200), default="")
    course: Mapped[str] = mapped_column(String(100), default="")
    jockey: Mapped[str] = mapped_column(String(120), default="")
    trainer: Mapped[str] = mapped_column(String(120), default="")

    user: Mapped["User"] = relationship("User", back_populates="paper_bets")
