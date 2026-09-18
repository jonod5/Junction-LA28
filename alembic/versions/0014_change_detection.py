"""Add change detection to the review queue + gold-standard flag (v1.7 Phase 3).

venue_extraction gains:
  - previous_value (nullable) — the stored value a "pending_change" draft
    proposes to replace; NULL for a brand-new field ("pending" status).
  - entity_id (nullable) — the specific target row a draft applies to.
    transit_access changes always carry this (Tier-1 change detection in
    app/services/venue_enrichment.py already knows exactly which row it's
    diffing against); parking_option/curb_dropoff/congestion_tdm still
    resolve lazily via app/services/venue_targets.py for a first-time
    ("pending") draft, since the row may not exist yet.
  - source_url and source_quote become nullable — Tier-1 change detection
    has a feed identifier, not a URL, and no prose citation to quote.

venue gains is_gold_standard (bool) — marks the hand-collected venues
app/validate_pipeline.py checks the pipeline's output against. Backfilled
True for every venue that exists at this migration, same reasoning as the
reviewed backfills in 0012/0013: everything that predates this pipeline
is hand-collected.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venue_extraction", sa.Column("previous_value", sa.Text(), nullable=True))
    op.add_column("venue_extraction", sa.Column("entity_id", sa.Integer(), nullable=True))
    op.alter_column("venue_extraction", "source_url", existing_type=sa.String(500), nullable=True)
    op.alter_column("venue_extraction", "source_quote", existing_type=sa.Text(), nullable=True)

    op.add_column("venue", sa.Column("is_gold_standard", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE venue SET is_gold_standard = TRUE")


def downgrade() -> None:
    op.drop_column("venue", "is_gold_standard")

    op.alter_column("venue_extraction", "source_quote", existing_type=sa.Text(), nullable=False)
    op.alter_column("venue_extraction", "source_url", existing_type=sa.String(500), nullable=False)
    op.drop_column("venue_extraction", "entity_id")
    op.drop_column("venue_extraction", "previous_value")
