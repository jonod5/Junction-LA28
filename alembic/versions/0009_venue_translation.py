"""Add venue_translation table for translated venue prose (v1.5 Phase 3).

English stays the system of record on venue/parking_option/curb_dropoff/
transit_access/congestion_tdm; this table only holds what a translation
*adds* per (entity_type, entity_id, field, language), so the API can fall
back to English whenever a row is missing.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "venue_translation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(50), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("entity_type", "entity_id", "field", "language", name="uq_venue_translation_key"),
    )
    op.create_index("ix_venue_translation_venue_id", "venue_translation", ["venue_id"])


def downgrade() -> None:
    op.drop_index("ix_venue_translation_venue_id", table_name="venue_translation")
    op.drop_table("venue_translation")
