"""Add itinerary + itinerary_tag tables for saved itineraries.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "itinerary",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("trip_date", sa.Date(), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("saved_plan", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_itinerary_user_id", "itinerary", ["user_id"])

    op.create_table(
        "itinerary_tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_itinerary_tag_user_name"),
    )
    op.create_index("ix_itinerary_tag_user_id", "itinerary_tag", ["user_id"])

    op.create_table(
        "itinerary_tag_link",
        sa.Column("itinerary_id", sa.Integer(), sa.ForeignKey("itinerary.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("itinerary_tag.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("itinerary_tag_link")
    op.drop_table("itinerary_tag")
    op.drop_index("ix_itinerary_user_id", table_name="itinerary")
    op.drop_table("itinerary")
