"""
Live transit endpoints — served cache-first from Redis.

  GET /api/vehicles           all live Metro vehicles (Swiftly GTFS-RT)
  GET /api/transit/live?line= running status for one line (for a transit step)

Both degrade gracefully: with no SWIFTLY_API_KEY configured (or a feed down)
they return a "not configured / scheduled" shape rather than erroring, so the
frontend falls back to Google's scheduled times.
"""

import logging

from fastapi import APIRouter, Query

from app.ingest import transit_rt

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/vehicles")
def get_vehicles():
    """Live Metro vehicle positions (cache-first).  Empty when unconfigured."""
    return transit_rt.get_vehicles()


@router.get("/api/transit/live")
def transit_live(line: str = Query(..., description="Transit line label, e.g. 'A Line' or '720'")):
    """Live running status for a single transit line."""
    return transit_rt.live_status_for_line(line)
