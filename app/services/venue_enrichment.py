"""
Tier-1 automated venue enrichment — GTFS + GBFS + OSM + computed cost.

The venue-data pipeline splits every field by how automatable it is:
  Tier 1 (this module) — feed-derived, no human in the loop. High confidence,
    written with reviewed=True immediately: nearest transit (GTFS static),
    nearby micromobility (GBFS), walking surroundings (OSM Overpass), walk
    time/distance and a ride-hail cost estimate (computed).
  Tier 2 (later phase) — LLM-extracted from source pages, reviewed=False
    until a human approves. Not touched by this module.
  Tier 3 (scaffold only) — official LA28 data, not yet available anywhere.

Ground rule this module upholds: feed data is written as fact (reviewed=True)
because it IS verifiable fact — a GTFS stop either exists at that location
or it doesn't. This is categorically different from Tier 2's LLM extraction,
which must never be auto-marked reviewed.

Idempotent by design: each TransitAccess row this module creates carries
`external_ref` = the GTFS stop_id it came from. Re-running enrich_venue()
looks up existing rows by (venue_id, external_ref) and updates them in
place rather than duplicating. Rows with external_ref=NULL are hand-
collected and this module never touches them.

Cost note: walk time/distance goes through the Directions proxy, which
means a real (though Redis-cached, 1h TTL) Google Directions call per
nearby stop. Fine for one venue or an occasional --all re-run; be mindful
before scripting frequent large-scale re-enrichment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.gbfs import get_nearby as gbfs_get_nearby
from app.ingest.gbfs import haversine_m
from app.ingest.osm import nearby_context, summarize_context
from app.models.gtfs import GtfsRoute, GtfsStop, GtfsStopTime, GtfsTrip
from app.models.venue import TransitAccess, Venue
from app.routers.directions import DirectionsError, fetch_directions
from app.services.fares import rideshare_estimate

log = logging.getLogger(__name__)

# Default walkable radius for "nearest transit" — matches the walkable
# cutoff already used for venue-transit map fitting on the frontend
# (see frontend's VENUE_TRANSIT "nearby" distance convention).
DEFAULT_TRANSIT_RADIUS_M = 1200
DEFAULT_TRANSIT_LIMIT = 5
DEFAULT_MICROMOBILITY_RADIUS_M = 600
DEFAULT_OSM_RADIUS_M = 300

# GTFS route_type codes we bother labeling distinctly (others fall back to
# "transit"). https://gtfs.org/schedule/reference/#routestxt
_ROUTE_TYPE_LABEL = {0: "tram", 1: "metro", 2: "rail", 3: "bus", 7: "funicular"}

_METERS_PER_DEGREE_LAT = 111_320.0


@dataclass
class NearbyStop:
    stop_id: str
    stop_name: str | None
    lat: float
    lng: float
    distance_m: float
    routes: list[dict] = field(default_factory=list)  # [{short_name, long_name, mode}]


def _bounding_box(lat: float, lng: float, radius_m: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng) — a cheap pre-filter before the
    exact haversine check; over-includes slightly at the corners, which is
    fine since every candidate still gets the exact distance check."""
    import math

    dlat = radius_m / _METERS_PER_DEGREE_LAT
    dlng = radius_m / (_METERS_PER_DEGREE_LAT * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def _routes_for_stop(db: Session, stop_id: str) -> list[dict]:
    """Distinct routes serving a stop, deduped by route_id."""
    route_ids = db.execute(
        select(GtfsTrip.route_id)
        .join(GtfsStopTime, GtfsStopTime.trip_id == GtfsTrip.trip_id)
        .where(GtfsStopTime.stop_id == stop_id)
        .distinct()
    ).scalars().all()
    if not route_ids:
        return []
    routes = db.execute(select(GtfsRoute).where(GtfsRoute.route_id.in_(route_ids))).scalars().all()
    return [
        {
            "route_id": r.route_id,
            "short_name": r.route_short_name,
            "long_name": r.route_long_name,
            "mode": _ROUTE_TYPE_LABEL.get(r.route_type, "transit"),
        }
        for r in routes
    ]


def find_nearest_transit(
    db: Session, lat: float, lng: float,
    radius_m: float = DEFAULT_TRANSIT_RADIUS_M, limit: int = DEFAULT_TRANSIT_LIMIT,
) -> list[NearbyStop]:
    """
    Nearest GTFS stops within radius_m, each with the routes serving it.

    No spatial index in this schema — a lat/lng bounding-box pre-filter
    (index-friendly range scan) narrows the candidate set, then exact
    haversine distance + the real radius cutoff runs in Python, same
    two-step pattern app.ingest.gbfs.get_nearby() already uses.

    Prefers parent stations (location_type=1) over their own child
    platforms when both are in range, so one physical station doesn't
    fragment into several near-duplicate results.
    """
    min_lat, max_lat, min_lng, max_lng = _bounding_box(lat, lng, radius_m)
    candidates = db.execute(
        select(GtfsStop).where(
            GtfsStop.stop_lat.between(min_lat, max_lat),
            GtfsStop.stop_lon.between(min_lng, max_lng),
        )
    ).scalars().all()

    in_range: list[tuple[GtfsStop, float]] = []
    for stop in candidates:
        if stop.stop_lat is None or stop.stop_lon is None:
            continue
        d = haversine_m(lat, lng, float(stop.stop_lat), float(stop.stop_lon))
        if d <= radius_m:
            in_range.append((stop, d))

    # Drop child platforms whose parent station is also in range — keep
    # whichever of the two is closer (usually the parent, but not always).
    parent_ids_present = {s.stop_id for s, _ in in_range if s.location_type == 1}
    filtered = [
        (s, d) for s, d in in_range
        if not (s.parent_station and s.parent_station in parent_ids_present)
    ]

    filtered.sort(key=lambda pair: pair[1])
    result: list[NearbyStop] = []
    for stop, dist in filtered[:limit]:
        result.append(NearbyStop(
            stop_id=stop.stop_id,
            stop_name=stop.stop_name,
            lat=float(stop.stop_lat),
            lng=float(stop.stop_lon),
            distance_m=round(dist, 1),
            routes=_routes_for_stop(db, stop.stop_id),
        ))
    return result


def _walk_time_and_cost(venue_lat: float, venue_lng: float, stop: NearbyStop) -> dict:
    """
    Walk time/distance to a stop via the Directions proxy, plus a ride-hail
    estimate for the same trip from the existing fare model. Falls back to
    straight-line distance / an assumed walking speed if Directions is
    unavailable (e.g. no API key configured) — labeled accordingly via the
    returned `source`, never silently swapped in as if it were routed.
    """
    origin = f"{venue_lat},{venue_lng}"
    destination = f"{stop.lat},{stop.lng}"
    try:
        walk = fetch_directions(origin, destination, "walking")
    except DirectionsError as exc:
        log.warning("Directions unavailable for walk time (%s -> %s): %s", origin, destination, exc)
        walk = None

    if walk:
        distance_m, duration_s = walk["distance_m"], walk["duration_s"]
        source = "directions_api"
    else:
        # Straight-line fallback: ~1.3 m/s average walking speed.
        distance_m = stop.distance_m
        duration_s = distance_m / 1.3
        source = "haversine_estimate"

    return {
        "distance_m": distance_m,
        "duration_s": duration_s,
        "walk_time_min": round(duration_s / 60),
        "rideshare_estimate_usd": rideshare_estimate(distance_m, duration_s),
        "source": source,
    }


@dataclass
class EnrichmentResult:
    venue_id: int
    stops_found: int
    rows_created: int
    rows_updated: int
    micromobility_count: int
    osm_note: str | None
    errors: list[str] = field(default_factory=list)


def enrich_venue(
    db: Session, venue: Venue,
    transit_radius_m: float = DEFAULT_TRANSIT_RADIUS_M,
    transit_limit: int = DEFAULT_TRANSIT_LIMIT,
) -> EnrichmentResult:
    """
    Populate Tier-1 TransitAccess rows for one venue from GTFS/GBFS/OSM,
    with provenance, and mark the venue as pipeline-reviewed.

    Idempotent: matches existing rows by (venue_id, external_ref=stop_id)
    and updates them rather than duplicating. Never touches hand-collected
    rows (external_ref IS NULL).
    """
    if venue.lat is None or venue.lng is None:
        raise ValueError(f"Venue {venue.id} has no coordinates — nothing to enrich from")
    venue_lat, venue_lng = float(venue.lat), float(venue.lng)

    errors: list[str] = []
    now = datetime.now(timezone.utc)

    stops = find_nearest_transit(db, venue_lat, venue_lng, transit_radius_m, transit_limit)

    micromobility = gbfs_get_nearby(venue_lat, venue_lng, DEFAULT_MICROMOBILITY_RADIUS_M)
    micro_note = (
        f"{len(micromobility['items'])} shared bike/scooter(s) within "
        f"{DEFAULT_MICROMOBILITY_RADIUS_M}m as of the last enrichment run."
        if micromobility["items"] else None
    )
    if micromobility.get("errors"):
        errors.extend(f"gbfs:{provider}: {msgs}" for provider, msgs in micromobility["errors"].items())

    osm = nearby_context(venue_lat, venue_lng, DEFAULT_OSM_RADIUS_M)
    osm_note = summarize_context(osm["elements"])
    if osm.get("error"):
        errors.append(f"osm: {osm['error']}")

    existing_by_ref: dict[str, TransitAccess] = {
        row.external_ref: row
        for row in venue.transit_accesses
        if row.external_ref is not None
    }

    rows_created = rows_updated = 0
    for stop in stops:
        walk = _walk_time_and_cost(venue_lat, venue_lng, stop)
        # Combine OSM surroundings + micromobility into one prose note —
        # neither has its own column on TransitAccess (see module docstring
        # in app/ingest/osm.py and the Phase-1 plan for why).
        transit_notes = " ".join(p for p in (micro_note, osm_note) if p) or None
        primary_route = stop.routes[0] if stop.routes else None
        line = ", ".join(r["short_name"] or r["long_name"] or r["route_id"] for r in stop.routes) or None
        bus_lines = ", ".join(
            r["short_name"] or r["long_name"] or r["route_id"]
            for r in stop.routes if r["mode"] == "bus"
        ) or None

        row = existing_by_ref.get(stop.stop_id)
        if row is None:
            row = TransitAccess(venue_id=venue.id, external_ref=stop.stop_id)
            db.add(row)
            rows_created += 1
        else:
            rows_updated += 1

        row.line = line
        row.mode = primary_route["mode"] if primary_route else "transit"
        row.stop_name = stop.stop_name
        row.walk_time_min = walk["walk_time_min"]
        row.bus_lines_serving = bus_lines
        row.gbfs_dock_description = micro_note
        row.transit_notes = transit_notes
        row.rideshare_estimate_usd = walk["rideshare_estimate_usd"]
        row.source = f"gtfs_static+{walk['source']}"
        row.retrieved_at = now
        row.confidence = "high" if walk["source"] == "directions_api" else "estimated"
        row.reviewed = True

    venue.retrieved_at = now
    venue.confidence = "high"
    venue.reviewed = True

    return EnrichmentResult(
        venue_id=venue.id,
        stops_found=len(stops),
        rows_created=rows_created,
        rows_updated=rows_updated,
        micromobility_count=len(micromobility["items"]),
        osm_note=osm_note,
        errors=errors,
    )
