"""Add unique constraint on sp_response(respondent_id, task_id).

A load-testing pass found this endpoint's "already answered" check races:
two near-simultaneous submits for the same task (double-click, a client
retry after a slow/timed-out response) both pass the check before either
commits, and both inserts succeed — silently duplicating a respondent's
choice rather than erroring. This constraint turns that into a catchable
IntegrityError (see app.routers.survey.record_choice's 409 handling)
instead of corrupting the research data.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_sp_response_respondent_task", "sp_response", ["respondent_id", "task_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_sp_response_respondent_task", "sp_response", type_="unique")
