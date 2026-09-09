"""Add Tier-2 LLM-extraction review queue (v1.7 Phase 2).

Adds the same provenance columns Phase 1 gave venue/transit_access
(retrieved_at, confidence, reviewed) to parking_option, curb_dropoff, and
congestion_tdm, so an approved extraction can carry provenance on the real
row exactly like Tier-1 does. Backfills existing rows to reviewed=True for
the same reason as migration 0012: every row that exists before this column
did is pre-pipeline hand-collected data, already verified through the
original collection process.

Also creates venue_extraction — the review queue itself. This table is the
ONLY place app/services/venue_extract.py writes to; a human decision via
app/routers/venue_review.py is what copies a value into parking_option /
curb_dropoff / congestion_tdm. Nothing here changes those tables' shape.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("parking_option", "curb_dropoff", "congestion_tdm"):
        op.add_column(table, sa.Column("retrieved_at", sa.DateTime(), nullable=True))
        op.add_column(table, sa.Column("confidence", sa.String(20), nullable=True))
        op.add_column(table, sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.execute(f"UPDATE {table} SET reviewed = TRUE")

    op.create_table(
        "venue_extraction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("venue_id", sa.Integer(), sa.ForeignKey("venue.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("extracted_value", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
    )
    # The queue listing endpoint always filters by venue and usually by status
    # ("show me this venue's pending drafts") — index the pair it actually queries.
    op.create_index("ix_venue_extraction_venue_status", "venue_extraction", ["venue_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_venue_extraction_venue_status", table_name="venue_extraction")
    op.drop_table("venue_extraction")

    for table in ("parking_option", "curb_dropoff", "congestion_tdm"):
        op.drop_column(table, "reviewed")
        op.drop_column(table, "confidence")
        op.drop_column(table, "retrieved_at")
