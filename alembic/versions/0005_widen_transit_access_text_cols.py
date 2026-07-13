"""Widen transit_access.line, stop_name, nearest_metro_station to Text.

VARCHAR(100/200) is too narrow for multi-line/multi-station seed values.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("transit_access", "line", type_=sa.Text(), existing_nullable=True)
    op.alter_column("transit_access", "stop_name", type_=sa.Text(), existing_nullable=True)
    op.alter_column(
        "transit_access", "nearest_metro_station", type_=sa.Text(), existing_nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "transit_access", "nearest_metro_station", type_=sa.String(200), existing_nullable=True
    )
    op.alter_column("transit_access", "stop_name", type_=sa.String(200), existing_nullable=True)
    op.alter_column("transit_access", "line", type_=sa.String(100), existing_nullable=True)
