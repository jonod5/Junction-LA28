"""
Pydantic request/response schemas.

Design choices:
- Kept in one file for the MVP; split into schemas/ package when the count
  grows past ~10 models.
- Numeric lat/lng are float in the API contract (not Decimal) so they
  serialise to JSON numbers without a custom encoder.
- from_attributes = True on every Out schema lets FastAPI build them directly
  from SQLAlchemy ORM instances without explicit .model_validate() calls.
- Nested Out schemas use lists (never Optional[list]) — an empty list is
  always the correct sentinel for "no related rows", not None.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Leg ─────────────────────────────────────────────────────────────────────

class LegOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_stop_id: int
    to_stop_id: int
    mode: str
    distance_m: int | None
    duration_s: int | None
    polyline: str | None


class LegUpsert(BaseModel):
    """Body for creating or replacing a leg between two stops."""
    from_stop_id: int
    to_stop_id: int
    mode: str
    distance_m: int | None = None
    duration_s: int | None = None
    polyline: str | None = None


# ── Stop ─────────────────────────────────────────────────────────────────────

class StopCreate(BaseModel):
    venue_id: int | None = None
    name: str
    lat: float
    lng: float


class StopReorder(BaseModel):
    stop_id: int
    order_index: int


class StopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int | None
    name: str
    lat: float
    lng: float
    order_index: int


# ── Trip ─────────────────────────────────────────────────────────────────────

class TripCreate(BaseModel):
    name: str
    user_id: str | None = None


class TripUpdate(BaseModel):
    name: str


class TripOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    user_id: str | None
    stops: list[StopOut] = []
    legs: list[LegOut] = []


# ── Venue detail ─────────────────────────────────────────────────────────────

class ParkingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lot_name: str | None
    is_official: bool
    price_min: float | None
    price_max: float | None
    price_notes: str | None
    pricing_basis: str | None
    has_surge_pricing: bool | None
    surge_notes: str | None
    is_closest_to_entrance: bool | None
    notes: str | None


class TransitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line: str | None
    mode: str | None
    stop_name: str | None
    walk_time_min: int | None
    nearest_metro_station: str | None
    bus_lines_serving: str | None
    bike_lane_nearby: bool | None
    gbfs_dock_description: str | None
    transit_notes: str | None


class CurbOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rideshare_zone_description: str | None
    rideshare_zone_open_window: str | None
    taxi_accessible_zone: str | None
    private_vehicle_dropoff: str | None
    no_stop_zones: str | None
    curbside_restrictions: str | None


class CongestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommended_arrival_hrs_before_min: float | None
    recommended_arrival_hrs_before_max: float | None
    arrival_notes: str | None
    high_congestion_entry_roads: str | None
    known_congestion_exit_roads: str | None
    general_tdm_notes: str | None


class VenueDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sport_use: str | None
    zone: str | None
    address: str | None
    lat: float | None
    lng: float | None
    total_spaces: int | None
    total_lots: int | None
    capacity_text: str | None
    games_time_access_notes: str | None
    # Program-level constant injected at serialisation time (not a DB column).
    games_time_parking_policy: str
    parking_options: list[ParkingOut] = []
    transit_accesses: list[TransitOut] = []
    curb_dropoffs: list[CurbOut] = []
    congestion_tdm: CongestionOut | None = None
