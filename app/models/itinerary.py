"""
Saved itinerary models — Itinerary, ItineraryTag.

Design choices:
- saved_plan is a generic SQLAlchemy JSON column (not postgresql.JSONB) —
  matches the User.id String-over-UUID precedent: JSONB is Postgres-only and
  would break the SQLite-backed test suite, while generic JSON works
  identically on both dialects with no functional loss for our access
  pattern (always read/written whole, never queried by key).
- saved_plan holds the full planner snapshot (ordered stops + the selected
  RouteOption per leg) verbatim, in the shape frontend/lib/store.tsx's
  TripContext already produces — the route engine's option shape is free to
  evolve without a migration, and reopening an itinerary is just "hand this
  blob back to the frontend," not a relational reconstruction.
- Upcoming vs Past is derived from trip_date at query time (see
  app.routers.itineraries), not stored, so "today" always reflects the
  moment of the request rather than the moment the row was saved.
- Tags are per-user (ItineraryTag.user_id), not global — two users can each
  have their own "Family" tag without collision. The link table is a plain
  many-to-many join, not a model, since it carries no attributes of its own.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

itinerary_tag_link = Table(
    "itinerary_tag_link",
    Base.metadata,
    Column("itinerary_id", Integer, ForeignKey("itinerary.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("itinerary_tag.id", ondelete="CASCADE"), primary_key=True),
)


class ItineraryTag(Base):
    __tablename__ = "itinerary_tag"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_itinerary_tag_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class Itinerary(Base):
    __tablename__ = "itinerary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trip_date: Mapped[date | None] = mapped_column(Date)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    saved_plan: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tags: Mapped[list["ItineraryTag"]] = relationship(secondary=itinerary_tag_link)
