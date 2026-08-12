"""Add stated-preference (SP) survey pipeline tables (v2 Phase 2a skeleton).

sp_survey / sp_choice_task / sp_alternative / sp_respondent / sp_response —
see app/models/sp.py for the full design rationale.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sp_survey",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("tasks_per_respondent", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sp_choice_task",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("sp_survey.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_code", sa.String(50), nullable=False),
        sa.Column("block_id", sa.String(50), nullable=True),
    )
    op.create_index("ix_sp_choice_task_survey_id", "sp_choice_task", ["survey_id"])
    op.create_index("ix_sp_choice_task_block_id", "sp_choice_task", ["block_id"])

    op.create_table(
        "sp_alternative",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("sp_choice_task.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alt_code", sa.String(50), nullable=False),
        sa.Column("mode_label", sa.String(200), nullable=False),
        sa.Column("travel_time_min", sa.Numeric(6, 1), nullable=True),
        sa.Column("cost_usd", sa.Numeric(8, 2), nullable=True),
        sa.Column("walk_time_min", sa.Numeric(6, 1), nullable=True),
        sa.Column("transfers", sa.Integer(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_sp_alternative_task_id", "sp_alternative", ["task_id"])

    op.create_table(
        "sp_respondent",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("sp_survey.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("block_id", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sp_respondent_survey_id", "sp_respondent", ["survey_id"])

    op.create_table(
        "sp_response",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "respondent_id", sa.String(36), sa.ForeignKey("sp_respondent.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("sp_choice_task.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "chosen_alternative_id", sa.Integer(), sa.ForeignKey("sp_alternative.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("shown_at", sa.DateTime(), nullable=False),
        sa.Column("chosen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sp_response_respondent_id", "sp_response", ["respondent_id"])
    op.create_index("ix_sp_response_task_id", "sp_response", ["task_id"])


def downgrade() -> None:
    op.drop_table("sp_response")
    op.drop_index("ix_sp_respondent_survey_id", table_name="sp_respondent")
    op.drop_table("sp_respondent")
    op.drop_table("sp_alternative")
    op.drop_index("ix_sp_choice_task_block_id", table_name="sp_choice_task")
    op.drop_index("ix_sp_choice_task_survey_id", table_name="sp_choice_task")
    op.drop_table("sp_choice_task")
    op.drop_table("sp_survey")
