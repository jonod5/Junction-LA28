"""Venue schema revision — capacity fields, price envelope, arrival range, source simplification.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── venue: add parking capacity + Games-time notes ──────────────────────
    op.add_column("venue", sa.Column("total_spaces", sa.Integer(), nullable=True))
    op.add_column("venue", sa.Column("total_lots", sa.Integer(), nullable=True))
    op.add_column("venue", sa.Column("capacity_text", sa.Text(), nullable=True))
    op.add_column("venue", sa.Column("games_time_access_notes", sa.Text(), nullable=True))

    # ── parking_option: remove per-timing price columns + lot-level space count;
    #    add unified price envelope + context fields ──────────────────────────
    op.drop_column("parking_option", "total_spaces")
    op.drop_column("parking_option", "price_event_day_min")
    op.drop_column("parking_option", "price_event_day_max")
    op.drop_column("parking_option", "price_advance_min")
    op.drop_column("parking_option", "price_advance_max")

    op.add_column("parking_option", sa.Column("price_min", sa.Numeric(8, 2), nullable=True))
    op.add_column("parking_option", sa.Column("price_max", sa.Numeric(8, 2), nullable=True))
    op.add_column("parking_option", sa.Column("price_notes", sa.Text(), nullable=True))
    op.add_column("parking_option", sa.Column("pricing_basis", sa.Text(), nullable=True))

    # ── congestion_tdm: replace single arrival field with min/max + notes ───
    op.drop_column("congestion_tdm", "recommended_arrival_hrs_before")

    op.add_column(
        "congestion_tdm",
        sa.Column("recommended_arrival_hrs_before_min", sa.Numeric(4, 1), nullable=True),
    )
    op.add_column(
        "congestion_tdm",
        sa.Column("recommended_arrival_hrs_before_max", sa.Numeric(4, 1), nullable=True),
    )
    op.add_column("congestion_tdm", sa.Column("arrival_notes", sa.Text(), nullable=True))

    # ── venue_source: collapse multi-row structure into primary/secondary URL ─
    op.drop_column("venue_source", "source_type")
    op.drop_column("venue_source", "url_or_document")
    op.drop_column("venue_source", "accessed_date")
    op.drop_column("venue_source", "notes")

    op.add_column("venue_source", sa.Column("primary_url", sa.Text(), nullable=True))
    op.add_column("venue_source", sa.Column("secondary_url", sa.Text(), nullable=True))


def downgrade() -> None:
    # ── venue_source: restore multi-row structure ────────────────────────────
    op.drop_column("venue_source", "primary_url")
    op.drop_column("venue_source", "secondary_url")

    op.add_column("venue_source", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("venue_source", sa.Column("accessed_date", sa.Date(), nullable=True))
    op.add_column(
        "venue_source",
        sa.Column("url_or_document", sa.Text(), nullable=True),
    )
    op.add_column(
        "venue_source",
        sa.Column("source_type", sa.String(20), nullable=True),
    )

    # ── congestion_tdm: restore single arrival field ─────────────────────────
    op.drop_column("congestion_tdm", "arrival_notes")
    op.drop_column("congestion_tdm", "recommended_arrival_hrs_before_max")
    op.drop_column("congestion_tdm", "recommended_arrival_hrs_before_min")

    op.add_column(
        "congestion_tdm",
        sa.Column("recommended_arrival_hrs_before", sa.Numeric(4, 1), nullable=True),
    )

    # ── parking_option: restore four-column price structure + space count ─────
    op.drop_column("parking_option", "pricing_basis")
    op.drop_column("parking_option", "price_notes")
    op.drop_column("parking_option", "price_max")
    op.drop_column("parking_option", "price_min")

    op.add_column(
        "parking_option",
        sa.Column("price_advance_max", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "parking_option",
        sa.Column("price_advance_min", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "parking_option",
        sa.Column("price_event_day_max", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "parking_option",
        sa.Column("price_event_day_min", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column("parking_option", sa.Column("total_spaces", sa.Integer(), nullable=True))

    # ── venue: remove capacity columns ───────────────────────────────────────
    op.drop_column("venue", "games_time_access_notes")
    op.drop_column("venue", "capacity_text")
    op.drop_column("venue", "total_lots")
    op.drop_column("venue", "total_spaces")
