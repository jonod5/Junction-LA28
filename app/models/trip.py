"""
Trip planner ORM models — Trip, Stop, Leg.

Design choices:
- Trip is a lightweight container; all spatial data lives on Stop.
- Stop.venue_id is nullable so custom (non-venue) waypoints are supported
  without schema changes.  ON DELETE SET NULL keeps the stop in place if a
  venue row is ever deleted.
- Leg is derived data (computed from the Directions API) and is persisted so
  the frontend can reload a trip without re-calling the proxy.  Re-computing
  a leg means a new Leg row (upsert by trip+from+to+mode).
- order_index is a plain integer; the API reorders by writing new values in
  a single transaction rather than renumbering in-place, which avoids unique
  constraint violations mid-reorder.
- user_id is nullable now; when auth is added it becomes a FK and can be
  indexed without a migration altering existing rows.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Trip(Base):
    __tablename__ = "trip"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # server_default so the DB sets the timestamp — avoids clock skew between
    # app containers and is correct on bulk inserts too.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    # Reserved for future auth; nullable so the MVP ships without a user table.
    user_id: Mapped[str | None] = mapped_column(String(100))

    stops: Mapped[list["Stop"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="Stop.order_index",  # always return stops in display order
    )
    legs: Mapped[list["Leg"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )


class Stop(Base):
    __tablename__ = "stop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trip.id", ondelete="CASCADE"), nullable=False
    )
    # Null = custom waypoint that isn't one of the 6 confirmed venues.
    venue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Coordinates stored on the stop so the map works even if the venue row
    # is updated or the FK is null.
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    lng: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    # 0-based; gaps are fine (e.g. 0, 1, 3) — sorted by value, not contiguity.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    trip: Mapped["Trip"] = relationship(back_populates="stops")
    # Two FKs pointing at the same table require explicit foreign_keys= to
    # avoid SQLAlchemy's AmbiguousForeignKeysError.
    legs_from: Mapped[list["Leg"]] = relationship(
        foreign_keys="Leg.from_stop_id", back_populates="from_stop"
    )
    legs_to: Mapped[list["Leg"]] = relationship(
        foreign_keys="Leg.to_stop_id", back_populates="to_stop"
    )


class Leg(Base):
    __tablename__ = "leg"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trip.id", ondelete="CASCADE"), nullable=False
    )
    from_stop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stop.id", ondelete="CASCADE"), nullable=False
    )
    to_stop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stop.id", ondelete="CASCADE"), nullable=False
    )
    # Matches Google Directions API mode values: driving|transit|walking|bicycling
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    # Google's encoded polyline format — decoded client-side by the map SDK.
    polyline: Mapped[str | None] = mapped_column(Text)

    trip: Mapped["Trip"] = relationship(back_populates="legs")
    from_stop: Mapped["Stop"] = relationship(
        foreign_keys=[from_stop_id], back_populates="legs_from"
    )
    to_stop: Mapped["Stop"] = relationship(
        foreign_keys=[to_stop_id], back_populates="legs_to"
    )
