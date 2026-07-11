"""
Mirror tables for GTFS static data.

These tables are populated by ingest/gtfs_static.py and are read-only at
runtime.  They are separate from the venue schema so the GTFS ingest can
be re-run (truncate + reload) without touching manually entered venue data.

Column names follow the GTFS spec field names exactly so CSV rows can be
inserted with minimal transformation.
"""

from sqlalchemy import Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GtfsStop(Base):
    __tablename__ = "gtfs_stop"

    # GTFS stop_id is a string (e.g. "80214")
    stop_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    stop_name: Mapped[str | None] = mapped_column(String(300))
    stop_lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    stop_lon: Mapped[float | None] = mapped_column(Numeric(9, 6))
    stop_desc: Mapped[str | None] = mapped_column(Text)
    zone_id: Mapped[str | None] = mapped_column(String(50))
    location_type: Mapped[int | None] = mapped_column(Integer)
    parent_station: Mapped[str | None] = mapped_column(String(50))


class GtfsRoute(Base):
    __tablename__ = "gtfs_route"

    route_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    agency_id: Mapped[str | None] = mapped_column(String(50))
    route_short_name: Mapped[str | None] = mapped_column(String(50))
    route_long_name: Mapped[str | None] = mapped_column(String(300))
    # GTFS route_type codes: 0=tram, 1=metro, 2=rail, 3=bus, 7=funicular …
    route_type: Mapped[int | None] = mapped_column(Integer)
    route_color: Mapped[str | None] = mapped_column(String(10))
    route_text_color: Mapped[str | None] = mapped_column(String(10))


class GtfsTrip(Base):
    __tablename__ = "gtfs_trip"

    trip_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    route_id: Mapped[str | None] = mapped_column(String(50))
    service_id: Mapped[str | None] = mapped_column(String(50))
    trip_headsign: Mapped[str | None] = mapped_column(String(300))
    direction_id: Mapped[int | None] = mapped_column(Integer)
    shape_id: Mapped[str | None] = mapped_column(String(50))


class GtfsStopTime(Base):
    __tablename__ = "gtfs_stop_time"

    # Integer surrogate PK — composite (trip_id, stop_sequence) would be
    # correct but makes bulk upserts awkward with SQLAlchemy Core.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(String(100), nullable=False)
    stop_id: Mapped[str] = mapped_column(String(50), nullable=False)
    # GTFS times can exceed 24:00:00 for overnight service; store as string.
    arrival_time: Mapped[str | None] = mapped_column(String(8))
    departure_time: Mapped[str | None] = mapped_column(String(8))
    stop_sequence: Mapped[int | None] = mapped_column(Integer)
    stop_headsign: Mapped[str | None] = mapped_column(String(300))
    pickup_type: Mapped[int | None] = mapped_column(Integer)
    drop_off_type: Mapped[int | None] = mapped_column(Integer)


# Indexes created at DDL time.  Both are required by the spec:
# trip_id index → look up all stops for a trip (used for route display)
# stop_id index → look up all trips through a stop (used for departure boards)
Index("ix_gtfs_stop_time_trip_id", GtfsStopTime.trip_id)
Index("ix_gtfs_stop_time_stop_id", GtfsStopTime.stop_id)
