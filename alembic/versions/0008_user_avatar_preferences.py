"""Add avatar_url and preferences to users.

preferences starts with just default_modes (planner onboarding mode
checklist) but is a generic JSON blob so future account preferences don't
need another migration.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column(
        "users",
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")
    op.drop_column("users", "avatar_url")
