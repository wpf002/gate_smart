"""
Watchlist — per-user follows of horses, trainers, and jockeys.

Owners are intentionally not supported: the NA feed carries no owner field.
Matching against race cards is by `entity_key` (a normalized name for
trainers/jockeys, or the horse registration id / normalized name for horses).
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# The entity kinds a user can follow. Owner is deliberately excluded — the NA
# racecard feed does not include owner data.
WATCHLIST_ENTITY_TYPES = ("horse", "trainer", "jockey")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_key", name="uq_watchlist_user_entity"),
        Index("ix_watchlist_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # One of WATCHLIST_ENTITY_TYPES.
    entity_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Match key: normalized name (trainers/jockeys) or registration id / normalized
    # name (horses). Lowercased, punctuation-stripped so feed spelling variants match.
    entity_key: Mapped[str] = mapped_column(String(160), nullable=False)
    # Human-readable name to display in the UI (original casing).
    entity_label: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
