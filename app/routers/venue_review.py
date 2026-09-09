"""
Admin review queue for Tier-2 LLM extractions (v1.7 Phase 2).

  GET  /api/venues/review-queue                — list drafts (default: pending)
  POST /api/venues/review-queue/{id}/decision   — approve / edit / reject a draft

This is the only code path allowed to write an extracted value into
ParkingOption / CurbDropoff / CongestionTdm — see VenueExtraction's
docstring in app/models/venue.py. app/services/venue_extract.py only ever
writes to the queue table itself.

Target-row resolution (_target_row):
- parking_option is genuinely many-per-venue (one row per lot/zone), so a
  draft targets the venue's "general" row — the one with lot_name IS NULL —
  creating it if none exists yet. Hand-collected lots always have a real
  lot_name, so this never collides with them.
- curb_dropoff and congestion_tdm are one-per-venue by convention (the
  latter enforced by a DB unique constraint), so a draft targets that
  venue's single row, creating it if none exists yet.

Overwrite protection (_apply_field): regardless of how the target row was
resolved, a draft may only be applied to a field that is currently empty.
This is what actually keeps hand-collected gold-standard data safe — if the
field already holds a value (hand-collected or previously approved), the
decision is refused with 409 rather than silently overwriting it. The
reviewer's option in that case is to reject the draft; correcting an
already-populated field is a deliberate action outside this queue, not
something an approve/edit click should do.

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
from app.models.venue import CongestionTdm, CurbDropoff, ParkingOption, VenueExtraction
from app.schemas import ReviewDecisionIn, VenueExtractionOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/venues/review-queue", tags=["venue-review"])

_VALID_DECISIONS = {"approve", "edit", "reject"}
_ENTITY_MODELS = {
    "parking_option": ParkingOption,
    "curb_dropoff": CurbDropoff,
    "congestion_tdm": CongestionTdm,
}


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
    if status != "all":
        query = query.where(VenueExtraction.status == status)
    query = query.order_by(VenueExtraction.created_at.desc())

    return db.execute(query).scalars().all()


def _target_row(db: Session, venue_id: int, entity_type: str):
    model = _ENTITY_MODELS[entity_type]
    if entity_type == "parking_option":
        row = db.execute(
            select(ParkingOption).where(ParkingOption.venue_id == venue_id, ParkingOption.lot_name.is_(None))
        ).scalars().first()
    else:
        row = db.execute(select(model).where(model.venue_id == venue_id)).scalars().first()

    if row is None:
        kwargs: dict = {"venue_id": venue_id}
        if entity_type in ("parking_option", "curb_dropoff"):
            # source is NOT NULL on these two — a placeholder until the
            # first field is actually applied fills it in below.
            kwargs["source"] = "llm_extract:pending"
        row = model(**kwargs)
        db.add(row)
        db.flush()
    return row


def _apply_field(row, field_name: str, value: str, source_url: str, confidence: Decimal | None, now: datetime) -> None:
    current = getattr(row, field_name)
    if current not in (None, ""):
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
    if not row.source or row.source == "llm_extract:pending":
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
    if draft.status != "pending":
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

    row = _target_row(db, draft.venue_id, draft.entity_type)
    _apply_field(row, draft.field_name, value_to_apply, draft.source_url, draft.confidence, now)

    draft.status = "edited" if body.decision == "edit" else "approved"
    draft.reviewed_at = now
    draft.reviewed_by = body.reviewed_by

    # Any other still-pending draft for this exact field is now moot — this
    # decision is the one that won.
    for other in db.execute(
        select(VenueExtraction).where(
            VenueExtraction.id != draft.id,
            VenueExtraction.venue_id == draft.venue_id,
            VenueExtraction.entity_type == draft.entity_type,
            VenueExtraction.field_name == draft.field_name,
            VenueExtraction.status == "pending",
        )
    ).scalars().all():
        other.status = "superseded"
        other.reviewed_at = now

    db.commit()
    db.refresh(draft)
    return draft
