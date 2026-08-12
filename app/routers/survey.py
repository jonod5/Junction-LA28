"""
Stated-preference (SP) survey API — /api/survey.

Endpoints: start a session, fetch the next unanswered task, record a
choice, mark a session complete, and (admin-only) export responses as CSV
for analysis. See app/models/sp.py for the schema and app/ingest_sp.py for
how surveys get loaded.

Anonymity: sessions never require sign-in. A signed-in user's id is only
ever attached to a respondent row when they explicitly opt in
(SessionStartRequest.attach_account) — the default, and the only path
today's frontend takes, is a bare anonymous UUID with no account link.

Task sequencing: a respondent's ordered task list is derived deterministically
from a stable hash of (respondent_id, task_id) rather than stored — see
_task_sequence_for. Same respondent always gets the same order back from
/next without needing a sixth "sequence" table.

Admin guard on /export: a shared-secret header (X-Admin-Key checked against
the SP_ADMIN_KEY env var), not a user/role system — this endpoint is for
Kapil to pull data directly, never called from the frontend.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user_optional
from app.db import get_db
from app.models.sp import SPAlternative, SPChoiceTask, SPRespondent, SPResponse, SPSurvey
from app.models.user import User
from app.schemas_sp import (
    AlternativeOut,
    ChoiceRequest,
    ChoiceTaskOut,
    CompleteResponse,
    NextTaskResponse,
    SessionStartRequest,
    SessionStartResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/survey", tags=["survey"])


def _task_sequence_for(db: Session, respondent: SPRespondent, survey: SPSurvey) -> list[SPChoiceTask]:
    """This respondent's ordered task list — deterministic, not stored."""
    query = db.query(SPChoiceTask).filter(SPChoiceTask.survey_id == survey.id)
    if respondent.block_id is None:
        query = query.filter(SPChoiceTask.block_id.is_(None))
    else:
        query = query.filter(SPChoiceTask.block_id == respondent.block_id)
    tasks = query.all()

    def sort_key(task: SPChoiceTask) -> str:
        return hashlib.md5(f"{respondent.id}:{task.id}".encode()).hexdigest()  # noqa: S324 — not crypto

    tasks.sort(key=sort_key)
    return tasks[: survey.tasks_per_respondent]


def _assign_block(db: Session, survey_id: int) -> str | None:
    """Balanced-random: put the new respondent in whichever block currently
    has the fewest respondents. None if the survey doesn't use blocks."""
    block_ids = [
        row[0] for row in
        db.query(SPChoiceTask.block_id).filter(SPChoiceTask.survey_id == survey_id).distinct()
        if row[0] is not None
    ]
    if not block_ids:
        return None

    counts = dict(
        db.query(SPRespondent.block_id, func.count(SPRespondent.id))
        .filter(SPRespondent.survey_id == survey_id, SPRespondent.block_id.isnot(None))
        .group_by(SPRespondent.block_id)
        .all()
    )
    min_count = min((counts.get(b, 0) for b in block_ids), default=0)
    candidates = [b for b in block_ids if counts.get(b, 0) == min_count]
    return random.choice(candidates)


def _alt_out(alt: SPAlternative) -> AlternativeOut:
    return AlternativeOut(
        id=alt.id,
        alt_code=alt.alt_code,
        mode_label=alt.mode_label,
        travel_time_min=float(alt.travel_time_min) if alt.travel_time_min is not None else None,
        cost_usd=float(alt.cost_usd) if alt.cost_usd is not None else None,
        walk_time_min=float(alt.walk_time_min) if alt.walk_time_min is not None else None,
        transfers=alt.transfers,
        extra=alt.extra or {},
    )


@router.post("/{survey_id}/session", response_model=SessionStartResponse)
def start_session(
    survey_id: int,
    body: SessionStartRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    survey = db.get(SPSurvey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")

    block_id = _assign_block(db, survey_id)
    respondent = SPRespondent(
        survey_id=survey_id,
        user_id=current_user.id if (body.attach_account and current_user) else None,
        block_id=block_id,
    )
    db.add(respondent)
    db.commit()
    db.refresh(respondent)

    total_tasks = len(_task_sequence_for(db, respondent, survey))
    return SessionStartResponse(
        respondent_id=respondent.id, survey_id=survey_id, block_id=block_id, total_tasks=total_tasks,
    )


def _get_respondent(db: Session, respondent_id: str) -> SPRespondent:
    respondent = db.get(SPRespondent, respondent_id)
    if not respondent:
        raise HTTPException(status_code=404, detail=f"Respondent {respondent_id} not found")
    return respondent


@router.get("/session/{respondent_id}/next", response_model=NextTaskResponse)
def next_task(respondent_id: str, db: Session = Depends(get_db)):
    respondent = _get_respondent(db, respondent_id)
    survey = db.get(SPSurvey, respondent.survey_id)
    sequence = _task_sequence_for(db, respondent, survey)
    total = len(sequence)

    answered_task_ids = {
        r[0] for r in db.query(SPResponse.task_id).filter(SPResponse.respondent_id == respondent_id).all()
    }

    for i, task in enumerate(sequence):
        if task.id not in answered_task_ids:
            return NextTaskResponse(
                task=ChoiceTaskOut(
                    id=task.id, task_code=task.task_code,
                    alternatives=[_alt_out(a) for a in task.alternatives],
                ),
                task_number=i + 1,
                total_tasks=total,
                completed=False,
            )

    return NextTaskResponse(task=None, task_number=total, total_tasks=total, completed=True)


@router.post("/session/{respondent_id}/choice", status_code=204)
def record_choice(respondent_id: str, body: ChoiceRequest, db: Session = Depends(get_db)):
    respondent = _get_respondent(db, respondent_id)
    survey = db.get(SPSurvey, respondent.survey_id)
    sequence_ids = {t.id for t in _task_sequence_for(db, respondent, survey)}
    if body.task_id not in sequence_ids:
        raise HTTPException(status_code=400, detail="This task is not part of this respondent's sequence")

    already = (
        db.query(SPResponse)
        .filter(SPResponse.respondent_id == respondent_id, SPResponse.task_id == body.task_id)
        .first()
    )
    if already:
        raise HTTPException(status_code=409, detail="This task has already been answered")

    alternative = db.get(SPAlternative, body.chosen_alternative_id)
    if not alternative or alternative.task_id != body.task_id:
        raise HTTPException(status_code=400, detail="chosen_alternative_id does not belong to task_id")

    db.add(SPResponse(
        respondent_id=respondent_id,
        task_id=body.task_id,
        chosen_alternative_id=body.chosen_alternative_id,
        shown_at=body.shown_at,
    ))
    db.commit()


@router.post("/session/{respondent_id}/complete", response_model=CompleteResponse)
def complete_session(respondent_id: str, db: Session = Depends(get_db)):
    respondent = _get_respondent(db, respondent_id)
    if respondent.completed_at is None:
        respondent.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(respondent)
    return CompleteResponse(respondent_id=respondent.id, completed_at=respondent.completed_at)


def _check_admin_key(x_admin_key: str | None) -> None:
    expected = os.environ.get("SP_ADMIN_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="SP_ADMIN_KEY is not configured")
    if not x_admin_key or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Admin-Key")


@router.get("/{survey_id}/export")
def export_responses(
    survey_id: int,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
):
    """
    CSV export, long format — one row per (recorded choice x alternative
    shown in that task), with a `chosen` 0/1 flag. This is the shape
    discrete-choice tooling (biogeme, mlogit, etc.) expects: every
    alternative a respondent saw is its own row, not pivoted wide, so the
    column set stays fixed regardless of how many alternatives a task has.
    """
    _check_admin_key(x_admin_key)

    survey = db.get(SPSurvey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")

    responses = (
        db.query(SPResponse, SPRespondent, SPChoiceTask)
        .join(SPRespondent, SPResponse.respondent_id == SPRespondent.id)
        .join(SPChoiceTask, SPResponse.task_id == SPChoiceTask.id)
        .filter(SPChoiceTask.survey_id == survey_id)
        .order_by(SPRespondent.id, SPChoiceTask.task_code)
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "respondent_id", "block_id", "task_code", "alt_code", "chosen",
        "mode_label", "travel_time_min", "cost_usd", "walk_time_min", "transfers", "extra",
        "shown_at", "chosen_at",
    ])
    for response, respondent, task in responses:
        for alt in task.alternatives:
            writer.writerow([
                respondent.id, respondent.block_id, task.task_code, alt.alt_code,
                1 if alt.id == response.chosen_alternative_id else 0,
                alt.mode_label, alt.travel_time_min, alt.cost_usd, alt.walk_time_min, alt.transfers,
                alt.extra or {},
                response.shown_at.isoformat(), response.chosen_at.isoformat(),
            ])

    buf.seek(0)
    filename = f"sp_export_survey_{survey_id}.csv"
    return StreamingResponse(
        buf, media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
