"""GET /api/vehicles — serve GTFS-RT vehicle positions, cache-first."""

import logging

from fastapi import APIRouter, HTTPException

from app.ingest.gtfs_rt import fetch_vehicles, get_cached_vehicles

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/vehicles")
def get_vehicles():
    """
    Return live vehicle positions.

    Serves from the Redis cache (30 s TTL).  On a cache miss, fetches the
    upstream GTFS-RT feed immediately and re-caches before responding.
    This keeps p99 latency low for the common case while staying correct
    when the key has just expired.
    """
    cached = get_cached_vehicles()
    if cached is not None:
        return {"source": "cache", "count": len(cached), "vehicles": cached}

    try:
        vehicles = fetch_vehicles()
    except Exception as exc:
        log.exception("GTFS-RT fetch failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Could not fetch vehicle positions"
        ) from exc

    return {"source": "live", "count": len(vehicles), "vehicles": vehicles}
