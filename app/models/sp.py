"""
Stated-preference (SP) survey pipeline — Phase 2a skeleton.

ORM models for: a survey/experiment (sp_survey), the choice situations
within it (sp_choice_task), the alternatives shown per task
(sp_alternative), an anonymous respondent session (sp_respondent), and the
recorded choices (sp_response).

Design choices:
- No separate "respondent's task sequence" table. A respondent's ordered
  task list is derived deterministically at request time from a stable hash
  of (respondent_id, task_id) — see app.routers.survey._task_sequence_for —
  rather than persisted, so the schema stays at exactly the five tables in
  the spec while still giving each respondent a fixed (repeatable) order.
- sp_alternative.extra is a generic JSON column (not postgresql.JSONB) —
  same reasoning as Itinerary.saved_plan: works identically on the
  SQLite-backed test suite and Postgres, and this column is always
  read/written whole, never queried by key.
- sp_respondent.id is an application-generated UUID string (String(36)),
  matching the users.id precedent, rather than a Postgres-native UUID type —
  keeps every SP table SQLite-test-compatible too.
- sp_respondent.user_id is nullable and only ever set when a signed-in user
  explicitly opts in (see the API layer) — anonymous is the default and the
  only path this phase's frontend takes.
- No PII is modeled anywhere here. Live data collection additionally
  requires IRB approval and real (non-placeholder) consent — see
  frontend/app/survey.tsx and docs/sp_survey_csv_format.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class SPSurvey(Base):
    __tablename__ = "sp_survey"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(1000))
    # How many tasks a single respondent completes — may be fewer than the
    # survey's total task count when tasks are split across blocks.
    tasks_per_respondent: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    tasks: Mapped[list["SPChoiceTask"]] = relationship(back_populates="survey", cascade="all, delete-orphan")


class SPChoiceTask(Base):
    """One choice situation. A respondent sees a sequence of these."""

    __tablename__ = "sp_choice_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sp_survey.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_code: Mapped[str] = mapped_column(String(50), nullable=False)
    # Experimental-design block — respondents are assigned to one block and
    # only see that block's tasks. NULL means "no blocking, single pool."
    block_id: Mapped[str | None] = mapped_column(String(50), index=True)

    survey: Mapped["SPSurvey"] = relationship(back_populates="tasks")
    alternatives: Mapped[list["SPAlternative"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class SPAlternative(Base):
    """One option within a choice task. One CSV row = one alternative."""

    __tablename__ = "sp_alternative"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sp_choice_task.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alt_code: Mapped[str] = mapped_column(String(50), nullable=False)
    mode_label: Mapped[str] = mapped_column(String(200), nullable=False)

    travel_time_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    walk_time_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    transfers: Mapped[int | None] = mapped_column(Integer)
    # Any CSV columns beyond the named attributes above — keeps the schema
    # open to whatever else Kapil's design includes without a migration.
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    task: Mapped["SPChoiceTask"] = relationship(back_populates="alternatives")


class SPRespondent(Base):
    """One anonymous survey-taking session."""

    __tablename__ = "sp_respondent"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    survey_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sp_survey.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Opt-in only — see app.routers.survey.start_session. NULL is the
    # default and expected case: anonymous, no account required.
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    block_id: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class SPResponse(Base):
    """One recorded choice."""

    __tablename__ = "sp_response"
    __table_args__ = (
        # Without this, two near-simultaneous submits for the same task
        # (double-click, a client retry after a slow/timed-out first
        # response) both pass the router's "already answered" check before
        # either commits, and BOTH inserts succeed — silently duplicating a
        # respondent's choice in the research data rather than erroring.
        # This turns that into a clean, catchable constraint violation
        # instead (see app.routers.survey.record_choice's IntegrityError
        # handling).
        UniqueConstraint("respondent_id", "task_id", name="uq_sp_response_respondent_task"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    respondent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sp_respondent.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sp_choice_task.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chosen_alternative_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sp_alternative.id", ondelete="CASCADE"), nullable=False
    )
    # Client-reported timestamps — when the task rendered vs. when the
    # respondent submitted their pick. Not used for anything security- or
    # correctness-critical, only for analysis (response latency).
    shown_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    chosen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
