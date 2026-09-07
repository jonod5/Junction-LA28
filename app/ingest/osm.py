"""
OpenStreetMap (Overpass API) — nearby surroundings for venue enrichment.

Used for the "surroundings" ingredient of Tier-1 auto-enrichment: named
entrances and pedestrian-relevant POIs near a venue, which get folded into
that venue's TransitAccess.transit_notes rather than stored as their own
column (see app/services/venue_enrichment.py).

Design mirrors gbfs.py:
  • Cache the raw Overpass response in Redis, keyed by rounded coordinates +
    radius so nearby-identical requests share a cache entry.
  • OSM tags change slowly — a much longer TTL than GBFS's live-inventory
    60s is correct here, not an oversight.
  • Never raises for upstream failures; callers get an empty result plus the
    error, so one flaky feed never blocks the rest of an enrichment run.
"""

import json
import logging

import httpx

from app.cache import get_redis

log = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# OSM tags change on the order of weeks/months, not seconds — cache long.
CACHE_TTL_S = 7 * 24 * 3600

ATTRIBUTION = "© OpenStreetMap contributors, ODbL — https://www.openstreetmap.org/copyright"

# Tags worth surfacing as walking/entrance context near a venue. Kept small
# and specific rather than "everything nearby" — this feeds a short prose
# note, not a POI directory.
_RELEVANT_TAGS = (
    'node["entrance"](around:{r},{lat},{lng});'
    'node["amenity"="bicycle_parking"](around:{r},{lat},{lng});'
    'node["highway"="elevator"](around:{r},{lat},{lng});'
)


def _cache_key(lat: float, lng: float, radius_m: int) -> str:
    # Round to ~11m precision — collapses near-duplicate coordinate jitter
    # (e.g. slightly different float precision) onto the same cache entry.
    return f"osm:nearby:{lat:.4f}:{lng:.4f}:{radius_m}"


def _query(lat: float, lng: float, radius_m: int) -> str:
    body = _RELEVANT_TAGS.format(r=radius_m, lat=lat, lng=lng)
    return f"[out:json][timeout:15];({body});out body;"


def _fetch(lat: float, lng: float, radius_m: int) -> dict:
    r = get_redis()
    key = _cache_key(lat, lng, radius_m)
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)

    # Overpass's public instance 406s requests without a descriptive
    # User-Agent — httpx's default ("python-httpx/...") gets rejected as
    # part of its anti-abuse filtering. Per Overpass's own usage policy.
    headers = {"User-Agent": "junction-la28-venue-enrichment/1.0 (github.com/jonod5/Junction-LA28)"}
    with httpx.Client(timeout=20, headers=headers) as client:
        resp = client.post(OVERPASS_URL, data={"data": _query(lat, lng, radius_m)})
        resp.raise_for_status()
        data = resp.json()

    r.setex(key, CACHE_TTL_S, json.dumps(data))
    return data


def nearby_context(lat: float, lng: float, radius_m: int = 300) -> dict:
    """
    Return {"elements": [...], "error": str|None} of nearby entrance /
    bike-parking / elevator nodes, tagged and named where OSM has a name.

    Never raises — a failed Overpass call comes back as an empty element
    list with `error` set, so callers can degrade gracefully.
    """
    try:
        data = _fetch(lat, lng, radius_m)
    except httpx.HTTPError as exc:
        log.warning("Overpass query failed for (%s, %s): %s", lat, lng, exc)
        return {"elements": [], "error": str(exc)}

    elements = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        elements.append({
            "id": el.get("id"),
            "lat": el.get("lat"),
            "lng": el.get("lon"),
            "name": tags.get("name"),
            "entrance": tags.get("entrance"),
            "amenity": tags.get("amenity"),
            "highway": tags.get("highway"),
        })
    return {"elements": elements, "error": None}


def summarize_context(elements: list[dict]) -> str | None:
    """
    Turn nearby_context()'s elements into a short, human-readable note —
    e.g. "Named entrance nearby: West Gate. Bicycle parking nearby."

    Returns None when there's nothing worth mentioning, so callers can skip
    appending an empty sentence.
    """
    named_entrances = [e["name"] for e in elements if e.get("entrance") and e.get("name")]
    has_bike_parking = any(e.get("amenity") == "bicycle_parking" for e in elements)
    has_elevator = any(e.get("highway") == "elevator" for e in elements)

    parts: list[str] = []
    if named_entrances:
        # De-dupe while preserving order; cap so this stays one short sentence.
        seen: list[str] = []
        for name in named_entrances:
            if name not in seen:
                seen.append(name)
        parts.append(f"Named entrance nearby: {', '.join(seen[:3])}.")
    if has_bike_parking:
        parts.append("Bicycle parking nearby.")
    if has_elevator:
        parts.append("Elevator access nearby.")

    return " ".join(parts) if parts else None
