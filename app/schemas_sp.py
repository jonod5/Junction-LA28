"""Pydantic schemas for the stated-preference (SP) survey API — /api/survey."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AlternativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alt_code: str
    mode_label: str
    travel_time_min: float | None
    cost_usd: float | None
    walk_time_min: float | None
    transfers: int | None
    extra: dict[str, Any]


class ChoiceTaskOut(BaseModel):
    id: int
    task_code: str
    alternatives: list[AlternativeOut]


class SessionStartRequest(BaseModel):
    # Opt-in only — see app.routers.survey.start_session. A signed-in user
    # who does NOT pass this stays anonymous like everyone else.
    attach_account: bool = False


class SessionStartResponse(BaseModel):
    respondent_id: str
    survey_id: int
    block_id: str | None
    total_tasks: int


class NextTaskResponse(BaseModel):
    task: ChoiceTaskOut | None
    task_number: int  # 1-indexed position in this respondent's sequence
    total_tasks: int
    completed: bool


class ChoiceRequest(BaseModel):
    task_id: int
    chosen_alternative_id: int
    shown_at: datetime


class CompleteResponse(BaseModel):
    respondent_id: str
    completed_at: datetime
