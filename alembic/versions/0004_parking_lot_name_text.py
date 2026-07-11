"""Widen parking_option.lot_name from VARCHAR(200) to Text.

Some venues list all lots in a single lot_name string that exceeds 200 chars.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("parking_option", "lot_name", type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("parking_option", "lot_name", type_=sa.String(200), existing_nullable=True)
