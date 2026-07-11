"""
GTFS-Realtime vehicle positions — LA Metro API v2 (JSON).

Fetches vehicle positions from https://api.metro.net/{agency_id}/vehicle_positions/all
for both bus (LACMTA) and rail (LACMTA_Rail), merges the results, and caches
the list in Redis under "gtfs:vehicles" with a 30-second TTL.

Design choices:
- Two agency IDs must be queried separately; results are merged before caching.
- The LA Metro API returns JSON (not protobuf), so gtfs-realtime-bindings is
  not used here.  The response is a list of vehicle objects; we normalise only
  the fields the frontend needs.
- Redis TTL matches the typical Metro API update interval (30 s).
- GTFS_RT_VEHICLES_URLS is a comma-separated list of full endpoint URLs so
  the caller can override both agencies or add future ones without code changes.
"""

import json
import logging
import os

import httpx
import redis as redis_lib

log = logging.getLogger(__name__)

CACHE_KEY = "gtfs:vehicles"
CACHE_TTL = 30  # seconds

# Fallback if the env var is not set.
_DEFAULT_URLS = (
    "https://api.metro.net/LACMTA/vehicle_positions/all,"
    "https://api.metro.net/LACMTA_Rail/vehicle_positions/all"
)


def _get_redis() -> redis_lib.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis_lib.from_url(url, decode_responses=True)


def _rt_urls() -> list[str]:
    raw = os.environ.get("GTFS_RT_VEHICLES_URLS") or _DEFAULT_URLS
    return [u.strip() for u in raw.split(",") if u.strip()]


def _parse_vehicle(obj: dict, agency: str) -> dict:
    """Normalise a single vehicle object from the Metro API response."""
    return {
        "agency": agency,
        "vehicle_id": obj.get("vehicle_id") or obj.get("id"),
        "trip_id": obj.get("trip_id"),
        "route_id": obj.get("route_id"),
        "lat": obj.get("latitude") or obj.get("lat"),
        "lng": obj.get("longitude") or obj.get("lon") or obj.get("lng"),
        "bearing": obj.get("bearing"),
        "vehicle_label": obj.get("vehicle_label") or obj.get("label"),
    }


def _fetch_one(client: httpx.Client, url: str) -> list[dict]:
    """Fetch one agency URL and return normalised vehicle dicts."""
    # Derive a short agency label from the URL path segment.
    agency = url.split("/")[3] if url.count("/") >= 3 else url
    log.info("Fetching vehicle positions from %s", url)

    api_key = os.environ.get("GTFS_RT_API_KEY", "")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = client.get(url, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    # The Metro API returns either a list directly or {"data": [...]} wrapper.
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("data") or data.get("features") or data.get("vehicles") or []
    else:
        records = []

    return [_parse_vehicle(r, agency) for r in records]


def fetch_vehicles() -> list[dict]:
    """
    Fetch vehicle positions for all configured agencies, merge, cache, return.
    """
    urls = _rt_urls()
    vehicles: list[dict] = []

    with httpx.Client(timeout=10) as client:
        for url in urls:
            try:
                vehicles.extend(_fetch_one(client, url))
            except httpx.HTTPError as exc:
                # Log and continue — one agency failing should not hide the other.
                log.warning("Vehicle fetch failed for %s: %s", url, exc)

    r = _get_redis()
    r.setex(CACHE_KEY, CACHE_TTL, json.dumps(vehicles))
    log.debug("Cached %d vehicles in Redis (TTL %ds)", len(vehicles), CACHE_TTL)
    return vehicles


def get_cached_vehicles() -> list[dict] | None:
    """Return the cached vehicle list, or None if the key has expired."""
    r = _get_redis()
    raw = r.get(CACHE_KEY)
    if raw is None:
        return None
    return json.loads(raw)
