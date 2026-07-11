"""
GET /api/places?query=  — server-side proxy to Google Places Text Search.

Design choices:
- The Google Maps key lives exclusively in the server environment; the client
  never sees it.  This also lets us add rate limiting and caching in one place
  without any client changes.
- We return only (name, address) — the minimum the frontend needs for
  autocomplete / display.  This reduces payload size and avoids leaking
  internal Place IDs that clients could use to bypass the proxy.
- httpx is used synchronously here; swap to AsyncClient + async def if the
  rest of the app goes async.
- TODO: add a Redis cache with a short TTL (e.g. 5 min) per query string to
  stay within the Places API free tier.  The stub comment below marks where.
- TODO: add a rate-limit middleware (e.g. slowapi) before exposing publicly.
"""

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)
router = APIRouter()

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"


@router.get("/api/places")
def search_places(
    query: str = Query(
        ..., min_length=1, max_length=200, description="Free-text search query"
    ),
):
    """
    Proxy Google Places Text Search and return trimmed results.
    The GOOGLE_MAPS_KEY env var is injected server-side; clients never see it.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Maps API key not configured")

    # TODO: check Redis cache here before making the upstream call.
    # cache_key = f"places:{query}"

    params = {
        "query": query,
        "key": api_key,
        # Bias results toward the LA region; does not restrict to it.
        "location": "34.0522,-118.2437",
        "radius": 50_000,
    }

    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(PLACES_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.exception("Places API request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Places API unavailable") from exc

    data = resp.json()
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        log.error("Places API error status: %s", data.get("status"))
        raise HTTPException(
            status_code=502, detail=f"Places API error: {data.get('status')}"
        )

    # Return only name + formatted_address — never pass raw Place data to
    # clients because it may contain billing-sensitive fields.
    results = [
        {
            "name": r.get("name"),
            "address": r.get("formatted_address"),
        }
        for r in data.get("results", [])
    ]

    # TODO: write results to Redis cache here with a short TTL.

    return {"query": query, "count": len(results), "results": results}
