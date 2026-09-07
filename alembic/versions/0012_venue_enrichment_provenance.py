"""Add automated-pipeline provenance columns (v1.7 Phase 1 — Tier-1 enrichment).

Adds retrieved_at / confidence / reviewed to venue and transit_access — the
two tables the enrichment pipeline (app/services/venue_enrichment.py)
actually writes to in this phase. Also adds transit_access.external_ref
(the upstream GTFS stop_id a pipeline-created row came from, so re-runs can
upsert instead of duplicate) and transit_access.rideshare_estimate_usd (a
modeled cost estimate alongside the transit option, from app.services.fares).

parking_option / congestion_tdm get the same provenance columns in a later
migration, once Tier-2 extraction (Phase 2) actually populates them.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venue", sa.Column("retrieved_at", sa.DateTime(), nullable=True))
    op.add_column("venue", sa.Column("confidence", sa.String(20), nullable=True))
    op.add_column("venue", sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("transit_access", sa.Column("rideshare_estimate_usd", sa.Numeric(8, 2), nullable=True))
    op.add_column("transit_access", sa.Column("external_ref", sa.String(100), nullable=True))
    op.add_column("transit_access", sa.Column("retrieved_at", sa.DateTime(), nullable=True))
    op.add_column("transit_access", sa.Column("confidence", sa.String(20), nullable=True))
    op.add_column("transit_access", sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Every transit_access row that exists AT THIS MIGRATION is pre-pipeline
    # hand-collected data (external_ref, which only pipeline-written rows
    # get, doesn't exist as a column until the line above) — genuinely
    # human-verified via the original collection process, just never through
    # this reviewed column. Backfill reviewed=True so the API's "never show
    # reviewed=False as fact" filter (added alongside Tier-2 in the next
    # phase) doesn't accidentally hide real, already-verified transit data.
    op.execute("UPDATE transit_access SET reviewed = TRUE")

    # Enrichment re-runs look up existing rows by (venue_id, external_ref) to
    # upsert instead of duplicate — index it since every re-run does this lookup.
    op.create_index("ix_transit_access_external_ref", "transit_access", ["external_ref"])


def downgrade() -> None:
    op.drop_index("ix_transit_access_external_ref", table_name="transit_access")
    op.drop_column("transit_access", "reviewed")
    op.drop_column("transit_access", "confidence")
    op.drop_column("transit_access", "retrieved_at")
    op.drop_column("transit_access", "external_ref")
    op.drop_column("transit_access", "rideshare_estimate_usd")

    op.drop_column("venue", "reviewed")
    op.drop_column("venue", "confidence")
    op.drop_column("venue", "retrieved_at")
