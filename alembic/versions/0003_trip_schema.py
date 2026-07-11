"""Add trip, stop, and leg tables.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── trip ─────────────────────────────────────────────────────────────────
    op.create_table(
        "trip",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        # server_default keeps the DB authoritative on timestamps.
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # Nullable until auth is wired up; index deferred to that migration.
        sa.Column("user_id", sa.String(100), nullable=True),
    )

    # ── stop ─────────────────────────────────────────────────────────────────
    op.create_table(
        "stop",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "trip_id",
            sa.Integer(),
            sa.ForeignKey("trip.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL so the stop survives if the venue row is deleted.
        sa.Column(
            "venue_id",
            sa.Integer(),
            sa.ForeignKey("venue.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    # Most common query: all stops for a trip, sorted by order_index.
    op.create_index("ix_stop_trip_order", "stop", ["trip_id", "order_index"])

    # ── leg ──────────────────────────────────────────────────────────────────
    op.create_table(
        "leg",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "trip_id",
            sa.Integer(),
            sa.ForeignKey("trip.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_stop_id",
            sa.Integer(),
            sa.ForeignKey("stop.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_stop_id",
            sa.Integer(),
            sa.ForeignKey("stop.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # driving | transit | walking | bicycling — matches Google Directions API
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        # Google's encoded polyline — decoded client-side by the map SDK.
        sa.Column("polyline", sa.Text(), nullable=True),
    )
    # Lookup by trip when rendering all legs on the map.
    op.create_index("ix_leg_trip", "leg", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_leg_trip", table_name="leg")
    op.drop_table("leg")
    op.drop_index("ix_stop_trip_order", table_name="stop")
    op.drop_table("stop")
    op.drop_table("trip")
