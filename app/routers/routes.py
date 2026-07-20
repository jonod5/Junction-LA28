"""
POST /api/routes/optimize — ranked multimodal options for one leg.

Thin HTTP layer over app.services.route_engine.  All the routing logic and the
(deterministic, no-LLM) scoring live in the engine; this router only validates
input, resolves an optional destination venue's parking price for the
park-and-ride cost, and maps engine errors to HTTP status codes.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.venue import Venue
from app.routers.directions import DirectionsError
from app.services import route_engine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/routes", tags=["routes"])


class Coord(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class RouteOptimizeRequest(BaseModel):
    origin: Coord
    destination: Coord
    # Allowed primary mode keys (see route_engine.MODE_LABEL).  None/empty means
    # "all modes allowed".  Modes not listed are filtered out before scoring.
    preferences: list[str] | None = None
    # Unix seconds; honoured for transit backbones (cache-bucketed to 5 min).
    departure_time: int | None = None
    # When the destination is one of our venues, its collected parking price
    # feeds the park-and-ride cost estimate.
    destination_venue_id: int | None = None


def _venue_parking_min(db: Session, venue_id: int | None) -> float | None:
    if venue_id is None:
        return None
    venue = db.get(Venue, venue_id)
    if not venue or not venue.parking_options:
        return None
    prices = [float(p.price_min) for p in venue.parking_options if p.price_min is not None]
    return min(prices) if prices else None


@router.post("/optimize")
def optimize_routes(body: RouteOptimizeRequest, db: Session = Depends(get_db)):
    """Return a deterministic, ranked set of multimodal route options."""
    venue_price_min = _venue_parking_min(db, body.destination_venue_id)
    try:
        return route_engine.optimize(
            origin=(body.origin.lat, body.origin.lng),
            destination=(body.destination.lat, body.destination.lng),
            preferences=body.preferences,
            departure_time=body.departure_time,
            destination_venue_price_min=venue_price_min,
        )
    except DirectionsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
