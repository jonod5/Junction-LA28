"""Initial schema — all venue and GTFS tables.

Revision ID: 0001
Revises:
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── venue (core identity table) ─────────────────────────────────────────
    op.create_table(
        "venue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sport_use", sa.String(200)),
        sa.Column("zone", sa.String(100)),
        sa.Column("address", sa.String(300)),
        sa.Column("lat", sa.Numeric(9, 6)),
        sa.Column("lng", sa.Numeric(9, 6)),
        sa.Column("collection_status", sa.String(50)),
        sa.Column("date_collected", sa.Date()),
        sa.Column("data_sources_summary", sa.Text()),
    )

    # ── parking_option (§ Parking) ───────────────────────────────────────────
    op.create_table(
        "parking_option",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lot_name", sa.String(200)),
        sa.Column("is_official", sa.Boolean(), server_default="true"),
        sa.Column("total_spaces", sa.Integer()),
        sa.Column("price_event_day_min", sa.Numeric(8, 2)),
        sa.Column("price_event_day_max", sa.Numeric(8, 2)),
        sa.Column("price_advance_min", sa.Numeric(8, 2)),
        sa.Column("price_advance_max", sa.Numeric(8, 2)),
        sa.Column("has_surge_pricing", sa.Boolean()),
        sa.Column("surge_notes", sa.Text()),
        sa.Column("is_closest_to_entrance", sa.Boolean()),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("date_collected", sa.Date()),
        sa.Column("verified_at", sa.DateTime()),
        sa.Column("verified_by", sa.String(50)),
        sa.Column("data_gaps", sa.Text()),
    )
    op.create_index("ix_parking_option_venue_id", "parking_option", ["venue_id"])

    # ── curb_dropoff (§ Curb & Pickup / Drop-off) ───────────────────────────
    op.create_table(
        "curb_dropoff",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rideshare_zone_description", sa.Text()),
        sa.Column("rideshare_zone_open_window", sa.String(200)),
        sa.Column("taxi_accessible_zone", sa.Text()),
        sa.Column("private_vehicle_dropoff", sa.Text()),
        sa.Column("no_stop_zones", sa.Text()),
        sa.Column("curbside_restrictions", sa.Text()),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("date_collected", sa.Date()),
        sa.Column("verified_at", sa.DateTime()),
        sa.Column("verified_by", sa.String(50)),
        sa.Column("data_gaps", sa.Text()),
    )
    op.create_index("ix_curb_dropoff_venue_id", "curb_dropoff", ["venue_id"])

    # ── transit_access (§ Transit Access) ───────────────────────────────────
    op.create_table(
        "transit_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line", sa.String(100)),
        sa.Column("mode", sa.String(50)),
        sa.Column("stop_name", sa.String(200)),
        sa.Column("walk_time_min", sa.Integer()),
        sa.Column("nearest_metro_station", sa.String(200)),
        sa.Column("bus_lines_serving", sa.Text()),
        sa.Column("bike_lane_nearby", sa.Boolean()),
        sa.Column("gbfs_dock_description", sa.Text()),
        sa.Column("transit_notes", sa.Text()),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("date_collected", sa.Date()),
        sa.Column("verified_at", sa.DateTime()),
        sa.Column("verified_by", sa.String(50)),
        sa.Column("data_gaps", sa.Text()),
    )
    op.create_index("ix_transit_access_venue_id", "transit_access", ["venue_id"])

    # ── congestion_tdm (§ Congestion & TDM) — one row per venue ─────────────
    op.create_table(
        "congestion_tdm",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("recommended_arrival_hrs_before", sa.Numeric(4, 1)),
        sa.Column("high_congestion_entry_roads", sa.Text()),
        sa.Column("known_congestion_exit_roads", sa.Text()),
        sa.Column("event_day_parking_surge", sa.Boolean()),
        sa.Column("past_congestion_refs", sa.Text()),
        sa.Column("general_tdm_notes", sa.Text()),
        sa.Column("source", sa.String(500)),
        sa.Column("date_collected", sa.Date()),
        sa.Column("verified_at", sa.DateTime()),
        sa.Column("verified_by", sa.String(50)),
        sa.Column("data_gaps", sa.Text()),
    )

    # ── venue_source (§ Sources & Verification) ──────────────────────────────
    op.create_table(
        "venue_source",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(20)),
        sa.Column("url_or_document", sa.Text()),
        sa.Column("accessed_date", sa.Date()),
        sa.Column("verified_by", sa.String(50)),
        sa.Column("verified_at", sa.Date()),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_venue_source_venue_id", "venue_source", ["venue_id"])

    # ── GTFS mirror tables ───────────────────────────────────────────────────
    op.create_table(
        "gtfs_stop",
        sa.Column("stop_id", sa.String(50), primary_key=True),
        sa.Column("stop_name", sa.String(300)),
        sa.Column("stop_lat", sa.Numeric(9, 6)),
        sa.Column("stop_lon", sa.Numeric(9, 6)),
        sa.Column("stop_desc", sa.Text()),
        sa.Column("zone_id", sa.String(50)),
        sa.Column("location_type", sa.Integer()),
        sa.Column("parent_station", sa.String(50)),
    )

    op.create_table(
        "gtfs_route",
        sa.Column("route_id", sa.String(50), primary_key=True),
        sa.Column("agency_id", sa.String(50)),
        sa.Column("route_short_name", sa.String(50)),
        sa.Column("route_long_name", sa.String(300)),
        sa.Column("route_type", sa.Integer()),
        sa.Column("route_color", sa.String(10)),
        sa.Column("route_text_color", sa.String(10)),
    )

    op.create_table(
        "gtfs_trip",
        sa.Column("trip_id", sa.String(100), primary_key=True),
        sa.Column("route_id", sa.String(50)),
        sa.Column("service_id", sa.String(50)),
        sa.Column("trip_headsign", sa.String(300)),
        sa.Column("direction_id", sa.Integer()),
        sa.Column("shape_id", sa.String(50)),
    )

    op.create_table(
        "gtfs_stop_time",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.String(100), nullable=False),
        sa.Column("stop_id", sa.String(50), nullable=False),
        sa.Column("arrival_time", sa.String(8)),
        sa.Column("departure_time", sa.String(8)),
        sa.Column("stop_sequence", sa.Integer()),
        sa.Column("stop_headsign", sa.String(300)),
        sa.Column("pickup_type", sa.Integer()),
        sa.Column("drop_off_type", sa.Integer()),
    )
    # Required by the spec — see models/gtfs.py for rationale
    op.create_index("ix_gtfs_stop_time_trip_id", "gtfs_stop_time", ["trip_id"])
    op.create_index("ix_gtfs_stop_time_stop_id", "gtfs_stop_time", ["stop_id"])


def downgrade() -> None:
    op.drop_table("gtfs_stop_time")
    op.drop_table("gtfs_trip")
    op.drop_table("gtfs_route")
    op.drop_table("gtfs_stop")
    op.drop_table("venue_source")
    op.drop_table("congestion_tdm")
    op.drop_table("transit_access")
    op.drop_table("curb_dropoff")
    op.drop_table("parking_option")
    op.drop_table("venue")
