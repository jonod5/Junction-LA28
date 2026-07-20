"""
GET /api/micromobility — live shared micromobility near a point + Metro Micro.

Combines two sources, clearly separated so the frontend can treat them
differently:
  • `items`      — LIVE GBFS vehicles/stations (Bird, Spin, Metro Bike Share)
                   within radius, cache-first from Redis, tagged by provider
                   and vehicle type, sorted nearest-first.
  • `metro_micro`— STATIC on-demand microtransit availability at the point
                   (no live API exists); zone + flat fare, labeled as such.

`metadata` carries GBFS attribution/license (required by the GBFS Data
License) plus any per-provider feed errors so the UI can degrade gracefully
and keep the hand-collected static zones as a labeled fallback.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.data import metro_micro
from app.ingest.gbfs import ATTRIBUTION, GBFS_LICENSE, MAX_TTL, get_nearby

log = logging.getLogger(__name__)
router = APIRouter(tags=["micromobility"])

# Guard-rail so a caller can't ask us to scan an absurd radius.
_MAX_RADIUS_M = 5000.0
_DEFAULT_RADIUS_M = 800.0


@router.get("/api/micromobility")
def get_micromobility(
    lat: float = Query(..., ge=-90, le=90, description="Latitude of the search centre"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude of the search centre"),
    radius_m: float = Query(_DEFAULT_RADIUS_M, gt=0, le=_MAX_RADIUS_M, description="Search radius in metres"),
):
    """
    Return live micromobility near (lat, lng) plus Metro Micro zone availability.

    Cache-first: each GBFS feed is hit at most once per its TTL (≤60s).  Never
    fails the whole response for a single feed being down — see metadata.errors.
    """
    try:
        near = get_nearby(lat, lng, radius_m)
    except Exception as exc:  # noqa: BLE001 — surface as 502, keep server up
        log.exception("Micromobility aggregation failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not fetch micromobility data") from exc

    return {
        "query": {"lat": lat, "lng": lng, "radius_m": radius_m},
        "count": len(near["items"]),
        "items": near["items"],
        "pricing": near["pricing"],
        "metro_micro": metro_micro.service_at_point(lat, lng),
        "metadata": {
            "attribution": ATTRIBUTION,
            "license": GBFS_LICENSE,
            "cache_ttl_max_s": MAX_TTL,
            "errors": near["errors"],
        },
    }
