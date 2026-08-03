"""
Pydantic schemas for saved itineraries — /api/itineraries.

Kept in a separate file rather than growing app/schemas.py, which already
flagged its own "split past ~10 models" threshold in its docstring.

Design choices:
- saved_plan is an untyped dict — its shape is owned by the frontend (see
  frontend/lib/store.tsx's TripContext: ordered stops + the selected
  RouteOption per leg). The backend stores and returns it verbatim rather
  than re-validating internals, so the route engine's option shape can keep
  evolving without a backend migration.
- ItineraryUpdate uses exclude_unset semantics in the router (all fields
  optional, no defaults meaningfully distinguishable from "not sent") so a
  PATCH can tell "field omitted" apart from "field explicitly set to null"
  (e.g. clearing trip_date).
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ItineraryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    trip_date: date | None = None
    is_pinned: bool = False
    tags: list[str] = []
    saved_plan: dict[str, Any] = {}


class ItineraryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    trip_date: date | None = None
    is_pinned: bool | None = None
    tags: list[str] | None = None
    saved_plan: dict[str, Any] | None = None


class ItineraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    trip_date: date | None
    is_pinned: bool
    saved_plan: dict[str, Any]
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class ItineraryListOut(BaseModel):
    items: list[ItineraryOut]
    total: int
    limit: int
    offset: int
