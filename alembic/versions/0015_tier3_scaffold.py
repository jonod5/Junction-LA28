"""Add Tier-3 official-data scaffold (v1.7).

Creates games_time_official — a one-per-venue slot for Games-time official
LA28 data (car-restricted zones, designated PUDO, shuttles, arrival
windows) that doesn't exist anywhere yet. Scaffold only: nothing populates
this table's fields today. source defaults to "official_pending" so a
present-but-empty row transparently communicates "we're waiting on this,"
distinct from a venue simply not having this table row at all.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "games_time_official",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False, unique=True,
        ),
        sa.Column("car_restricted_zones", sa.Text(), nullable=True),
        sa.Column("designated_pudo", sa.Text(), nullable=True),
        sa.Column("shuttles", sa.Text(), nullable=True),
        sa.Column("arrival_windows", sa.Text(), nullable=True),
        sa.Column("source", sa.String(500), nullable=False, server_default="official_pending"),
        sa.Column("retrieved_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("games_time_official")
