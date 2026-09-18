"""
Shared target-row resolution for the review-queue pipeline (v1.7 Phase 3).

Used both by app/services/venue_extract.py, to check whether a field it's
about to draft already has a value (deciding "pending" vs "pending_change"
— see VenueExtraction's docstring), and by app/routers/venue_review.py, to
find the row a decision should actually apply to.

parking_option is genuinely multi-row per venue (one per lot/zone), so a
pipeline-owned draft targets the venue's "general" row — the one with
lot_name IS NULL — creating it lazily only when a decision is applied
(find_target_row() never creates; get_or_create_target_row() does). Hand-
collected lots always have a real lot_name, so this never collides with
them. curb_dropoff and congestion_tdm are one-per-venue by convention
(congestion_tdm enforced by a DB unique constraint), so a draft targets
that venue's single row the same lazy way.

transit_access is different: Tier-1 change detection
(app/services/venue_enrichment.py) only ever drafts a change against a row
that already exists, and always knows its id up front, so both functions
just require entity_id for it rather than guessing.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.venue import CongestionTdm, CurbDropoff, ParkingOption, TransitAccess

ENTITY_MODELS = {
    "parking_option": ParkingOption,
    "curb_dropoff": CurbDropoff,
    "congestion_tdm": CongestionTdm,
    "transit_access": TransitAccess,
}


def find_target_row(db: Session, venue_id: int, entity_type: str, entity_id: int | None = None):
    """Read-only lookup — never creates a row. Returns None if nothing exists yet."""
    if entity_id is not None:
        return db.get(ENTITY_MODELS[entity_type], entity_id)
    if entity_type == "transit_access":
        return None  # always resolved by entity_id — see module docstring
    if entity_type == "parking_option":
        return db.execute(
            select(ParkingOption).where(ParkingOption.venue_id == venue_id, ParkingOption.lot_name.is_(None))
        ).scalars().first()
    model = ENTITY_MODELS[entity_type]
    return db.execute(select(model).where(model.venue_id == venue_id)).scalars().first()


def get_or_create_target_row(db: Session, venue_id: int, entity_type: str, entity_id: int | None = None):
    """
    Same resolution as find_target_row(), but creates a fresh row when none
    exists for parking_option/curb_dropoff/congestion_tdm. Only safe to
    call when actually applying a decision (see app/routers/venue_review.py)
    — extraction itself only ever reads, via find_target_row().
    """
    if entity_type == "transit_access":
        row = db.get(TransitAccess, entity_id) if entity_id is not None else None
        if row is None:
            raise ValueError("transit_access changes require an existing row (entity_id)")
        return row

    row = find_target_row(db, venue_id, entity_type, entity_id)
    if row is not None:
        return row

    model = ENTITY_MODELS[entity_type]
    kwargs: dict = {"venue_id": venue_id}
    if entity_type in ("parking_option", "curb_dropoff"):
        kwargs["source"] = "llm_extract:pending"  # NOT NULL on these two
    row = model(**kwargs)
    db.add(row)
    db.flush()
    return row
