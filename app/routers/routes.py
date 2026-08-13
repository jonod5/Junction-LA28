"""
POST /api/routes/optimize — ranked multimodal options for one leg.

Thin HTTP layer over app.services.route_engine.  All the routing logic and the
(deterministic, no-LLM) scoring live in the engine; this router only validates
input and maps engine errors to HTTP status codes.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.rate_limit import rate_limit
from app.routers.directions import DirectionsError
from app.services import route_engine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/routes", tags=["routes"])

# A single call here can fan out to 4-6+ Google Directions calls internally
# (one per candidate mode) — a lower per-minute cap than /api/directions'
# reflects that higher per-request cost. Own scope, own env var: a user
# actively planning hits both endpoints and neither should eat the other's
# budget.
OPTIMIZE_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_OPTIMIZE_PER_MIN", "15"))


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
    # App locale code (see frontend/lib/i18n.ts); forwarded to Google so
    # turn-by-turn steps come back in the caller's language. Unsupported or
    # missing falls back to English (app.routers.directions._normalize_language).
    language: str | None = None


@router.post("/optimize", dependencies=[Depends(rate_limit("routes_optimize", OPTIMIZE_RATE_LIMIT, 60))])
def optimize_routes(body: RouteOptimizeRequest):
    """Return a deterministic, ranked set of multimodal route options."""
    try:
        return route_engine.optimize(
            origin=(body.origin.lat, body.origin.lng),
            destination=(body.destination.lat, body.destination.lng),
            preferences=body.preferences,
            departure_time=body.departure_time,
            language=body.language,
        )
    except DirectionsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
