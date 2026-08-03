"""
Saved itinerary CRUD — /api/itineraries

Endpoints:
  POST   /api/itineraries              create (snapshot of the current plan)
  GET    /api/itineraries              list — paginated, filterable, sortable
  GET    /api/itineraries/{id}         get one
  PATCH  /api/itineraries/{id}         rename / re-tag / re-pin / update snapshot
  DELETE /api/itineraries/{id}         delete

Design choices:
- Every route requires get_current_user, and every query is scoped to
  current_user.id server-side — the id in the URL is never trusted alone.
  A mismatched owner returns 404, not 403, so an itinerary's existence isn't
  leaked to a user who doesn't own it.
- Upcoming/Past is derived from trip_date vs today at request time (never
  stored), so it's always correct regardless of when the row was saved.
  Undated itineraries (trip_date is null) count as Upcoming — there's no
  date for them to have passed.
- Pinned itineraries always sort first; the requested sort/order is the
  secondary key within that split.
- Tags are get-or-create per user by plain name — no separate
  tag-management endpoint needed for the MVP.
"""

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models.itinerary import Itinerary, ItineraryTag
from app.models.user import User
from app.schemas_itinerary import ItineraryCreate, ItineraryListOut, ItineraryOut, ItineraryUpdate

router = APIRouter(prefix="/api/itineraries", tags=["itineraries"])


def _get_owned_itinerary_or_404(itinerary_id: int, user: User, db: Session) -> Itinerary:
    itinerary = (
        db.query(Itinerary)
        .filter(Itinerary.id == itinerary_id, Itinerary.user_id == user.id)
        .first()
    )
    if not itinerary:
        raise HTTPException(status_code=404, detail=f"Itinerary {itinerary_id} not found")
    return itinerary


def _resolve_tags(names: list[str], user: User, db: Session) -> list[ItineraryTag]:
    """Get-or-create per-user tags by name, de-duplicated and stripped."""
    unique_names = {n.strip() for n in names if n.strip()}
    if not unique_names:
        return []
    existing = (
        db.query(ItineraryTag)
        .filter(ItineraryTag.user_id == user.id, ItineraryTag.name.in_(unique_names))
        .all()
    )
    existing_by_name = {t.name: t for t in existing}
    tags = []
    for name in unique_names:
        tag = existing_by_name.get(name)
        if tag is None:
            tag = ItineraryTag(user_id=user.id, name=name)
            db.add(tag)
            db.flush()  # assign an id before it's linked into itinerary.tags
        tags.append(tag)
    return tags


def _out(itinerary: Itinerary) -> ItineraryOut:
    return ItineraryOut(
        id=itinerary.id,
        name=itinerary.name,
        trip_date=itinerary.trip_date,
        is_pinned=itinerary.is_pinned,
        saved_plan=itinerary.saved_plan,
        tags=sorted(t.name for t in itinerary.tags),
        created_at=itinerary.created_at,
        updated_at=itinerary.updated_at,
    )


@router.post("", response_model=ItineraryOut, status_code=201)
def create_itinerary(
    body: ItineraryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itinerary = Itinerary(
        user_id=user.id,
        name=body.name,
        trip_date=body.trip_date,
        is_pinned=body.is_pinned,
        saved_plan=body.saved_plan,
    )
    itinerary.tags = _resolve_tags(body.tags, user, db)
    db.add(itinerary)
    db.commit()
    db.refresh(itinerary)
    return _out(itinerary)


@router.get("", response_model=ItineraryListOut)
def list_itineraries(
    status: Literal["upcoming", "past", "all"] = "all",
    tag: str | None = None,
    sort: Literal["trip_date", "created_at", "updated_at"] = "trip_date",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = dt.date.today()
    query = db.query(Itinerary).filter(Itinerary.user_id == user.id)

    if status == "upcoming":
        query = query.filter((Itinerary.trip_date.is_(None)) | (Itinerary.trip_date >= today))
    elif status == "past":
        query = query.filter(Itinerary.trip_date.is_not(None), Itinerary.trip_date < today)

    if tag:
        query = query.join(Itinerary.tags).filter(ItineraryTag.name == tag)

    total = query.count()

    sort_col = {
        "trip_date": Itinerary.trip_date,
        "created_at": Itinerary.created_at,
        "updated_at": Itinerary.updated_at,
    }[sort]
    sort_col = sort_col.asc() if order == "asc" else sort_col.desc()

    items = (
        query.order_by(Itinerary.is_pinned.desc(), sort_col)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ItineraryListOut(items=[_out(i) for i in items], total=total, limit=limit, offset=offset)


@router.get("/{itinerary_id}", response_model=ItineraryOut)
def get_itinerary(itinerary_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(_get_owned_itinerary_or_404(itinerary_id, user, db))


@router.patch("/{itinerary_id}", response_model=ItineraryOut)
def update_itinerary(
    itinerary_id: int,
    body: ItineraryUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    itinerary = _get_owned_itinerary_or_404(itinerary_id, user, db)
    # exclude_unset lets a PATCH tell "field omitted" apart from "field
    # explicitly set to null" — e.g. clearing trip_date vs leaving it alone.
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates:
        itinerary.name = updates["name"]
    if "trip_date" in updates:
        itinerary.trip_date = updates["trip_date"]
    if "is_pinned" in updates:
        itinerary.is_pinned = updates["is_pinned"]
    if "saved_plan" in updates:
        itinerary.saved_plan = updates["saved_plan"]
    if "tags" in updates:
        itinerary.tags = _resolve_tags(updates["tags"], user, db)
    db.commit()
    db.refresh(itinerary)
    return _out(itinerary)


@router.delete("/{itinerary_id}", status_code=204)
def delete_itinerary(itinerary_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    itinerary = _get_owned_itinerary_or_404(itinerary_id, user, db)
    db.delete(itinerary)
    db.commit()
