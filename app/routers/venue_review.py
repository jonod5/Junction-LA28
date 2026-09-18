"""
Admin review queue for Tier-1 change detection and Tier-2 extraction
(v1.7 Phases 2-3).

  GET  /api/venues/review-queue                — list drafts (default: pending)
  POST /api/venues/review-queue/{id}/decision   — approve / edit / reject a draft

This is the only code path allowed to write into ParkingOption /
CurbDropoff / CongestionTdm / TransitAccess on a draft's behalf — see
VenueExtraction's docstring in app/models/venue.py. Neither
app/services/venue_extract.py (Tier-2) nor app/services/venue_enrichment.py
(Tier-1 change detection) ever writes to those tables directly; both only
ever write to the queue table.

Target-row resolution is shared with venue_extract.py in
app/services/venue_targets.py — see that module's docstring for how each
entity_type resolves its row.

Two kinds of decision, by draft.status:
- "pending" (previous_value is None) — a field with no existing value.
  _apply_field refuses with 409 if the target field somehow already has
  one; this is what keeps hand-collected gold-standard data safe from a
  first-time draft landing on the wrong row.
- "pending_change" (previous_value is set) — a field that already had a
  value, and the pipeline computed a different one (Tier-1 re-enrichment,
  or Tier-2 re-extraction against an already-approved field). Approving
  this is EXPECTED to overwrite — that's the point — but only if the field
  still equals previous_value; if something else changed it since this
  draft was drafted, the decision is refused with 409 and the reviewer is
  told to re-run detection rather than apply a decision made against
  stale context.

Admin guard mirrors app/routers/survey.py's X-Admin-Key pattern, with its
own env var (VENUE_ADMIN_KEY) since venue-data review and survey-export are
different privilege domains — one key leaking shouldn't expose the other.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.venue import VenueExtraction
from app.schemas import ReviewDecisionIn, VenueExtractionOut
from app.services.venue_targets import get_or_create_target_row

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/venues/review-queue", tags=["venue-review"])

_VALID_DECISIONS = {"approve", "edit", "reject"}
_PENDING_STATUSES = {"pending", "pending_change"}


def _check_admin_key(x_admin_key: str | None) -> None:
    expected = os.environ.get("VENUE_ADMIN_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="VENUE_ADMIN_KEY is not configured")
    if not x_admin_key or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Admin-Key")


def _confidence_label(score: Decimal | float | None) -> str | None:
    if score is None:
        return None
    score = float(score)
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


@router.get("", response_model=list[VenueExtractionOut])
def list_review_queue(
    venue_id: int | None = Query(None),
    status: str = Query("pending"),
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
):
    _check_admin_key(x_admin_key)

    query = select(VenueExtraction)
    if venue_id is not None:
        query = query.where(VenueExtraction.venue_id == venue_id)
    if status == "pending":
        # The two "needs a decision" states, shown together by default —
        # see module docstring for what distinguishes them.
        query = query.where(VenueExtraction.status.in_(_PENDING_STATUSES))
    elif status != "all":
        query = query.where(VenueExtraction.status == status)
    query = query.order_by(VenueExtraction.created_at.desc())

    return db.execute(query).scalars().all()


def _apply_field(
    row, field_name: str, value: str, source_url: str | None, confidence: Decimal | None,
    now: datetime, expected_previous: str | None,
) -> None:
    current = getattr(row, field_name)
    current_str = str(current) if current is not None else None

    if expected_previous is not None:
        # A sanctioned change (status="pending_change") — overwriting is
        # the point, but only if nothing else touched this field since the
        # draft was created.
        if current_str != expected_previous:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{field_name} no longer matches what this change was drafted against "
                    f"(expected {expected_previous!r}, found {current_str!r}) — re-run detection "
                    "and re-review instead of applying a stale decision."
                ),
            )
    elif current not in (None, ""):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{field_name} already has a value on this row — refusing to overwrite existing "
                "(possibly hand-collected) data. Reject this draft or edit the row directly instead."
            ),
        )

    setattr(row, field_name, value)
    # Row-level provenance only, not per-field — see module docstring on the
    # granularity tradeoff. The queue row (with its own source_url/quote)
    # stays the permanent per-field record regardless.
    if source_url and (not row.source or row.source == "llm_extract:pending"):
        row.source = f"llm_extract:{source_url}"
    row.retrieved_at = now
    row.confidence = _confidence_label(confidence)
    row.reviewed = True


@router.post("/{extraction_id}/decision", response_model=VenueExtractionOut)
def decide(
    extraction_id: int,
    body: ReviewDecisionIn,
    db: Session = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
):
    _check_admin_key(x_admin_key)

    if body.decision not in _VALID_DECISIONS:
        raise HTTPException(status_code=422, detail=f"decision must be one of {sorted(_VALID_DECISIONS)}")

    draft = db.get(VenueExtraction, extraction_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Extraction {extraction_id} not found")
    if draft.status not in _PENDING_STATUSES:
        raise HTTPException(status_code=409, detail=f"Extraction {extraction_id} was already {draft.status}")

    now = datetime.now(timezone.utc)

    if body.decision == "reject":
        draft.status = "rejected"
        draft.reviewed_at = now
        draft.reviewed_by = body.reviewed_by
        db.commit()
        db.refresh(draft)
        return draft

    if body.decision == "edit":
        if not body.corrected_value or not body.corrected_value.strip():
            raise HTTPException(status_code=422, detail="corrected_value is required for an edit decision")
        value_to_apply = body.corrected_value.strip()
        draft.corrected_value = value_to_apply
    else:
        value_to_apply = draft.extracted_value

    row = get_or_create_target_row(db, draft.venue_id, draft.entity_type, draft.entity_id)
    _apply_field(row, draft.field_name, value_to_apply, draft.source_url, draft.confidence, now, draft.previous_value)
    if draft.entity_id is None:
        draft.entity_id = row.id

    draft.status = "edited" if body.decision == "edit" else "approved"
    draft.reviewed_at = now
    draft.reviewed_by = body.reviewed_by

    # Any other still-outstanding draft for this exact field is now moot —
    # this decision is the one that won.
    for other in db.execute(
        select(VenueExtraction).where(
            VenueExtraction.id != draft.id,
            VenueExtraction.venue_id == draft.venue_id,
            VenueExtraction.entity_type == draft.entity_type,
            VenueExtraction.field_name == draft.field_name,
            VenueExtraction.status.in_(_PENDING_STATUSES),
        )
    ).scalars().all():
        other.status = "superseded"
        other.reviewed_at = now

    db.commit()
    db.refresh(draft)
    return draft
