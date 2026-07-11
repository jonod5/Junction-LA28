"""
Trip + Stop CRUD — /api/trips

Endpoints:
  POST   /api/trips                          create trip
  GET    /api/trips/{id}                     get trip with stops + legs
  PATCH  /api/trips/{id}                     rename trip
  DELETE /api/trips/{id}                     delete trip + cascade
  POST   /api/trips/{id}/stops               add stop
  DELETE /api/trips/{id}/stops/{stop_id}     remove stop
  PATCH  /api/trips/{id}/stops/reorder       reorder stops

Design choices:
- No pagination on stops — a trip is unlikely to have more than ~20 stops;
  loading all with the trip is the right default.
- Leg rows are NOT created here; the frontend calls /api/directions, gets
  polyline+distance+duration, then POSTs a LegUpsert to store the result.
  This keeps the CRUD router fast (no upstream API calls) and makes legs
  re-computable on demand.
- Reorder uses a single transaction to write all new order_index values
  atomically so no intermediate state violates a unique constraint.
- 404 responses use a shared helper to keep error shapes consistent.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.trip import Leg, Stop, Trip
from app.schemas import LegOut, LegUpsert, StopCreate, StopOut, StopReorder, TripCreate, TripOut, TripUpdate

router = APIRouter(prefix="/api/trips", tags=["trips"])


def _get_trip_or_404(trip_id: int, db: Session) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")
    return trip


def _get_stop_or_404(stop_id: int, trip_id: int, db: Session) -> Stop:
    stop = db.get(Stop, stop_id)
    if not stop or stop.trip_id != trip_id:
        raise HTTPException(status_code=404, detail=f"Stop {stop_id} not found on trip {trip_id}")
    return stop


# ── Trip CRUD ────────────────────────────────────────────────────────────────

@router.post("", response_model=TripOut, status_code=201)
def create_trip(body: TripCreate, db: Session = Depends(get_db)):
    """Create a new empty trip."""
    trip = Trip(name=body.name, user_id=body.user_id)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: int, db: Session = Depends(get_db)):
    """Return trip with all stops (ordered) and legs."""
    return _get_trip_or_404(trip_id, db)


@router.patch("/{trip_id}", response_model=TripOut)
def update_trip(trip_id: int, body: TripUpdate, db: Session = Depends(get_db)):
    """Rename a trip."""
    trip = _get_trip_or_404(trip_id, db)
    trip.name = body.name
    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    """Delete trip — stops and legs cascade via FK."""
    trip = _get_trip_or_404(trip_id, db)
    db.delete(trip)
    db.commit()


# ── Stop CRUD ────────────────────────────────────────────────────────────────

@router.post("/{trip_id}/stops", response_model=StopOut, status_code=201)
def add_stop(trip_id: int, body: StopCreate, db: Session = Depends(get_db)):
    """
    Append a stop to the trip.

    order_index is set to max(existing) + 1 so the new stop lands at the
    bottom without the caller needing to know the current count.
    """
    trip = _get_trip_or_404(trip_id, db)
    # Compute next order index from the already-loaded relationship.
    next_order = max((s.order_index for s in trip.stops), default=-1) + 1
    stop = Stop(
        trip_id=trip_id,
        venue_id=body.venue_id,
        name=body.name,
        lat=body.lat,
        lng=body.lng,
        order_index=next_order,
    )
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop


@router.delete("/{trip_id}/stops/{stop_id}", status_code=204)
def remove_stop(trip_id: int, stop_id: int, db: Session = Depends(get_db)):
    """
    Remove a stop and orphan any legs that reference it.

    Legs referencing this stop are deleted via FK CASCADE (from_stop_id /
    to_stop_id both have ondelete="CASCADE").  The frontend should re-compute
    the affected leg after deletion.
    """
    stop = _get_stop_or_404(stop_id, trip_id, db)
    db.delete(stop)
    db.commit()


@router.patch("/{trip_id}/stops/reorder", response_model=TripOut)
def reorder_stops(trip_id: int, body: list[StopReorder], db: Session = Depends(get_db)):
    """
    Update order_index for multiple stops in one transaction.

    The client sends the full desired order as [{stop_id, order_index}].
    Any stop not in the list keeps its current order_index unchanged.
    """
    trip = _get_trip_or_404(trip_id, db)
    # Build a lookup to avoid N queries.
    stop_map = {s.id: s for s in trip.stops}
    for item in body:
        if item.stop_id in stop_map:
            stop_map[item.stop_id].order_index = item.order_index
    db.commit()
    db.refresh(trip)
    return trip


# ── Leg upsert ───────────────────────────────────────────────────────────────

@router.put("/{trip_id}/legs", response_model=LegOut, status_code=201)
def upsert_leg(trip_id: int, body: LegUpsert, db: Session = Depends(get_db)):
    """
    Store or replace the routing result for a stop pair + mode.

    The frontend calls /api/directions, receives distance/duration/polyline,
    then calls this endpoint to persist it.  Existing legs for the same
    (trip, from, to, mode) triple are replaced rather than appended.
    """
    _get_trip_or_404(trip_id, db)
    # Delete any existing leg for this exact pair+mode.
    existing = (
        db.query(Leg)
        .filter_by(trip_id=trip_id, from_stop_id=body.from_stop_id, to_stop_id=body.to_stop_id, mode=body.mode)
        .first()
    )
    if existing:
        db.delete(existing)
        db.flush()

    leg = Leg(
        trip_id=trip_id,
        from_stop_id=body.from_stop_id,
        to_stop_id=body.to_stop_id,
        mode=body.mode,
        distance_m=body.distance_m,
        duration_s=body.duration_s,
        polyline=body.polyline,
    )
    db.add(leg)
    db.commit()
    db.refresh(leg)
    return leg
