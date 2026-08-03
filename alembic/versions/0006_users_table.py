"""Add users table — local mirror of Supabase Auth identities.

id is the Supabase auth.users UUID itself (not a local serial PK) so
Trip/Itinerary FKs can reference it directly with no lookup. Stored as a
plain String(36), matching the existing Trip.user_id precedent, rather than
Postgres's native UUID type.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("users")
