"""
GET /api/venues/{id} — full venue detail for the info panel.

Design choices:
- Returns the full venue detail in a single call so the info panel can render
  without a waterfall of follow-up requests.
- GAMES_TIME_PARKING_POLICY is injected at serialisation time (it's a Python
  constant, not a DB column) so the client always gets the current value
  without a separate /config call.
- Parking options, transit accesses, curb dropoffs, and congestion are all
  loaded via SQLAlchemy relationship (eager via joined load would also work;
  the default lazy load is fine for a single-venue endpoint).
- Float conversion on lat/lng/price_min/price_max: SQLAlchemy returns Decimal
  for Numeric columns; Pydantic coerces them to float automatically when
  from_attributes=True, but we convert explicitly here to be safe with any
  future serialisation path.
- 404 uses the same pattern as the trips router for consistency.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.venue import (
    GAMES_TIME_PARKING_POLICY,
    Venue,
)
from app.schemas import (
    CongestionOut,
    CurbOut,
    ParkingOut,
    TransitOut,
    VenueDetailOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/venues", tags=["venues"])


def _float(val) -> float | None:
    """Convert Decimal or None to float for JSON serialisation."""
    return float(val) if val is not None else None


@router.get("/{venue_id}", response_model=VenueDetailOut)
def get_venue(venue_id: int, db: Session = Depends(get_db)):
    """
    Return full venue detail: identity, parking, transit, curb, congestion,
    games_time_access_notes, and the program-level parking policy constant.
    """
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail=f"Venue {venue_id} not found")

    # Build nested schemas from the ORM relationships.
    parking = [
        ParkingOut(
            id=p.id,
            lot_name=p.lot_name,
            is_official=p.is_official,
            price_min=_float(p.price_min),
            price_max=_float(p.price_max),
            price_notes=p.price_notes,
            pricing_basis=p.pricing_basis,
            has_surge_pricing=p.has_surge_pricing,
            surge_notes=p.surge_notes,
            is_closest_to_entrance=p.is_closest_to_entrance,
            notes=p.notes,
        )
        for p in venue.parking_options
    ]

    transit = [
        TransitOut(
            id=t.id,
            line=t.line,
            mode=t.mode,
            stop_name=t.stop_name,
            walk_time_min=t.walk_time_min,
            nearest_metro_station=t.nearest_metro_station,
            bus_lines_serving=t.bus_lines_serving,
            bike_lane_nearby=t.bike_lane_nearby,
            gbfs_dock_description=t.gbfs_dock_description,
            transit_notes=t.transit_notes,
        )
        for t in venue.transit_accesses
    ]

    curb = [
        CurbOut(
            id=c.id,
            rideshare_zone_description=c.rideshare_zone_description,
            rideshare_zone_open_window=c.rideshare_zone_open_window,
            taxi_accessible_zone=c.taxi_accessible_zone,
            private_vehicle_dropoff=c.private_vehicle_dropoff,
            no_stop_zones=c.no_stop_zones,
            curbside_restrictions=c.curbside_restrictions,
        )
        for c in venue.curb_dropoffs
    ]

    cong: CongestionOut | None = None
    if venue.congestion_tdm:
        td = venue.congestion_tdm
        cong = CongestionOut(
            id=td.id,
            recommended_arrival_hrs_before_min=_float(td.recommended_arrival_hrs_before_min),
            recommended_arrival_hrs_before_max=_float(td.recommended_arrival_hrs_before_max),
            arrival_notes=td.arrival_notes,
            high_congestion_entry_roads=td.high_congestion_entry_roads,
            known_congestion_exit_roads=td.known_congestion_exit_roads,
            general_tdm_notes=td.general_tdm_notes,
        )

    return VenueDetailOut(
        id=venue.id,
        name=venue.name,
        sport_use=venue.sport_use,
        zone=venue.zone,
        address=venue.address,
        lat=_float(venue.lat),
        lng=_float(venue.lng),
        total_spaces=venue.total_spaces,
        total_lots=venue.total_lots,
        capacity_text=venue.capacity_text,
        games_time_access_notes=venue.games_time_access_notes,
        # Inject program-level constant — not stored per-venue in the DB.
        games_time_parking_policy=GAMES_TIME_PARKING_POLICY,
        parking_options=parking,
        transit_accesses=transit,
        curb_dropoffs=curb,
        congestion_tdm=cong,
    )
