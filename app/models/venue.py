"""
ORM models mirroring the five sections of the Venue Data Collection sheet:
  1. Venue             — core identity + venue-level parking capacity
  2. ParkingOption     — § Parking (one row per lot / zone)
  3. CurbDropoff       — § Curb & Pickup/Drop-off
  4. TransitAccess     — § Transit Access
  5. CongestionTdm     — § Congestion & TDM
  6. VenueSource       — § Sources & Verification (one row per venue)

No values are seeded here — see app/seed_venues.py.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# ---------------------------------------------------------------------------
# Program-level constant — applies equally to all LA28 venues.
# Store here, NOT as a DB column; all venues share the same policy.
# ---------------------------------------------------------------------------
GAMES_TIME_PARKING_POLICY = (
    "No spectator parking at venues during LA28 Games. "
    "Attendees must use transit, sanctioned park-and-ride, or active transport."
)


class Venue(Base):
    __tablename__ = "venue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sport_use: Mapped[str | None] = mapped_column(String(200))
    zone: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Venue-level parking capacity (from "Total parking spaces" / "Total parking lots" rows)
    total_spaces: Mapped[int | None] = mapped_column(Integer)
    total_lots: Mapped[int | None] = mapped_column(Integer)
    capacity_text: Mapped[str | None] = mapped_column(Text)  # raw phrase from doc

    # Venue-specific Games-time shuttle / park-and-ride logistics (LA28-specific)
    games_time_access_notes: Mapped[str | None] = mapped_column(Text)

    # Collection metadata
    collection_status: Mapped[str | None] = mapped_column(String(50))
    date_collected: Mapped[date | None] = mapped_column(Date)
    data_sources_summary: Mapped[str | None] = mapped_column(Text)

    # Relationships
    parking_options: Mapped[list["ParkingOption"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    curb_dropoffs: Mapped[list["CurbDropoff"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    transit_accesses: Mapped[list["TransitAccess"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    congestion_tdm: Mapped["CongestionTdm | None"] = relationship(
        back_populates="venue", cascade="all, delete-orphan", uselist=False
    )
    sources: Mapped[list["VenueSource"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )


class ParkingOption(Base):
    """One row per lot / zone."""

    __tablename__ = "parking_option"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    lot_name: Mapped[str | None] = mapped_column(Text)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)

    # Numeric price envelope (lowest / highest across all event types and purchase timing)
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    # Full event-type / advance-vs-gate breakdown verbatim from doc
    price_notes: Mapped[str | None] = mapped_column(Text)
    # Provenance caveat — e.g. "UCLA Football 11/8/2025 — not confirmed LA28 Olympic pricing"
    pricing_basis: Mapped[str | None] = mapped_column(Text)

    has_surge_pricing: Mapped[bool | None] = mapped_column(Boolean)
    surge_notes: Mapped[str | None] = mapped_column(Text)
    is_closest_to_entrance: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    venue: Mapped["Venue"] = relationship(back_populates="parking_options")


class CurbDropoff(Base):
    __tablename__ = "curb_dropoff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    rideshare_zone_description: Mapped[str | None] = mapped_column(Text)
    rideshare_zone_open_window: Mapped[str | None] = mapped_column(String(200))
    taxi_accessible_zone: Mapped[str | None] = mapped_column(Text)
    private_vehicle_dropoff: Mapped[str | None] = mapped_column(Text)
    no_stop_zones: Mapped[str | None] = mapped_column(Text)
    curbside_restrictions: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    venue: Mapped["Venue"] = relationship(back_populates="curb_dropoffs")


class TransitAccess(Base):
    __tablename__ = "transit_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    line: Mapped[str | None] = mapped_column(String(100))
    mode: Mapped[str | None] = mapped_column(String(50))
    stop_name: Mapped[str | None] = mapped_column(String(200))
    walk_time_min: Mapped[int | None] = mapped_column(Integer)

    nearest_metro_station: Mapped[str | None] = mapped_column(String(200))
    bus_lines_serving: Mapped[str | None] = mapped_column(Text)
    bike_lane_nearby: Mapped[bool | None] = mapped_column(Boolean)
    gbfs_dock_description: Mapped[str | None] = mapped_column(Text)
    transit_notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    venue: Mapped["Venue"] = relationship(back_populates="transit_accesses")


class CongestionTdm(Base):
    """One row per venue (1-to-1)."""

    __tablename__ = "congestion_tdm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Arrival time envelope — overall min/max across all lot types / event types
    recommended_arrival_hrs_before_min: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    recommended_arrival_hrs_before_max: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    # Authoritative detail: lot vs gate vs shuttle, per event type, verbatim from doc
    arrival_notes: Mapped[str | None] = mapped_column(Text)

    high_congestion_entry_roads: Mapped[str | None] = mapped_column(Text)
    known_congestion_exit_roads: Mapped[str | None] = mapped_column(Text)
    event_day_parking_surge: Mapped[bool | None] = mapped_column(Boolean)
    past_congestion_refs: Mapped[str | None] = mapped_column(Text)
    general_tdm_notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str | None] = mapped_column(String(500))
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    venue: Mapped["Venue"] = relationship(back_populates="congestion_tdm")


class VenueSource(Base):
    """One row per venue — primary and secondary source URLs."""

    __tablename__ = "venue_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    primary_url: Mapped[str | None] = mapped_column(Text)
    secondary_url: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    verified_at: Mapped[date | None] = mapped_column(Date)

    venue: Mapped["Venue"] = relationship(back_populates="sources")
