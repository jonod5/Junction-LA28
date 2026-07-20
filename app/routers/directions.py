"""
GET /api/directions — server-side proxy to Google Directions API.

Design choices:
- The GOOGLE_MAPS_KEY never leaves the server; the frontend calls this proxy
  instead of Google directly.  This also lets us add rate-limiting and caching
  in one place without any client changes.
- We return only {distance_m, duration_s, polyline} — exactly what the Leg
  model needs.  Stripping the full Google response reduces payload size and
  avoids exposing billing-sensitive fields.
- Redis cache with a 1-hour TTL covers the common case of a user toggling
  between modes on the same stop pair.  Directions between fixed venue pairs
  are extremely stable; 1 h is safe.
- Cache key encodes origin, destination, and mode so different modes never
  collide.  Coordinates are rounded to 5 decimal places (~1 m precision)
  before hashing to prevent trivially different float representations from
  busting the cache.
- A 502 (not 500) is returned when Google is unreachable — the client is the
  upstream from the browser's perspective, and 502 is semantically correct for
  a bad gateway response.
- ZERO_RESULTS (no route found) returns 404 with a clear message rather than
  an empty 200, so the frontend can show a useful error state.
"""

import hashlib
import json
import logging
import os
import re
from enum import StrEnum

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.cache import get_redis

log = logging.getLogger(__name__)
router = APIRouter(tags=["directions"])

DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
CACHE_TTL = 3600  # 1 hour — venue-to-venue routes are stable


class TravelMode(StrEnum):
    driving = "driving"
    transit = "transit"
    walking = "walking"
    bicycling = "bicycling"


def _cache_key(origin: str, destination: str, mode: str) -> str:
    # Round coordinates to 5 dp to collapse trivially different floats.
    def _norm(coord: str) -> str:
        parts = coord.split(",")
        if len(parts) == 2:
            try:
                return f"{float(parts[0]):.5f},{float(parts[1]):.5f}"
            except ValueError:
                pass
        return coord

    raw = f"directions:{_norm(origin)}:{_norm(destination)}:{mode}"
    # Hash to cap key length and avoid special characters.
    return "dir:" + hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 — not crypto


_SKIP_INSTRUCTIONS = frozenset({"restricted usage road", "restricted usage road."})

# Compass words Google prefixes on the first walking step
_COMPASS = r"(?:north|south|east|west|northeast|northwest|southeast|southwest)"


def _strip_html(text: str) -> str:
    """Remove HTML tags from Google's html_instructions, keeping block elements separated."""
    if not text:
        return ""
    # Block-level tags become spaces so adjacent words don't merge
    text = re.sub(r"<(?:div|p|br)\b[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:div|p)>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_instruction(instruction: str, maneuver: str) -> str:
    """Make Google navigation instructions friendlier for tourists."""
    if not instruction:
        return instruction
    # "Head northwest on X toward Y" → "Continue on X"
    # Only on steps with no explicit maneuver (the initial heading step)
    if not maneuver:
        instruction = re.sub(
            rf"^Head\s+{_COMPASS}\w*\s+on\s+",
            "Continue on ",
            instruction,
            flags=re.IGNORECASE,
        )
    # Drop "toward X" suffix — redundant given the next step
    instruction = re.sub(r"\s+toward\s+.+$", "", instruction, flags=re.IGNORECASE)
    return instruction.strip()


_SKIP_PATTERN = re.compile(
    r"\s+(?:" + "|".join(re.escape(n) for n in _SKIP_INSTRUCTIONS) + r")\.?\s*$",
    re.IGNORECASE,
)


def _extract_steps(leg: dict) -> list[dict]:
    steps = []
    for step in leg.get("steps", []):
        raw_instruction = _strip_html(step.get("html_instructions", ""))
        # Strip administrative notes appended by Google as inline divs (e.g. "Restricted usage road")
        raw_instruction = _SKIP_PATTERN.sub("", raw_instruction).strip()
        maneuver = step.get("maneuver", "") or ""

        # Skip steps whose entire content is an administrative note
        if raw_instruction.lower().rstrip(".") in _SKIP_INSTRUCTIONS:
            continue

        instruction = _clean_instruction(raw_instruction, maneuver)
        if not instruction:
            continue

        s: dict = {
            "mode": step.get("travel_mode", "").lower(),
            "instruction": instruction,
            "maneuver": maneuver,
            "distance_m": step.get("distance", {}).get("value", 0),
            "duration_s": step.get("duration", {}).get("value", 0),
            "polyline": step.get("polyline", {}).get("points", ""),
        }
        td = step.get("transit_details")
        if td:
            line = td.get("line", {})
            vehicle = line.get("vehicle", {})
            s["transit_line"] = line.get("name")
            s["transit_line_short"] = line.get("short_name")
            s["transit_vehicle"] = vehicle.get("type", "").lower()
            s["transit_color"] = line.get("color")
            s["departure_stop"] = td.get("departure_stop", {}).get("name")
            s["arrival_stop"] = td.get("arrival_stop", {}).get("name")
            s["num_stops"] = td.get("num_stops")
            s["headsign"] = td.get("headsign")
        if step.get("steps"):
            sub = [
                _clean_instruction(_strip_html(ss.get("html_instructions", "")), ss.get("maneuver", "") or "")
                for ss in step["steps"]
            ]
            s["sub_steps"] = [x for x in sub if x and x.lower().rstrip(".") not in _SKIP_INSTRUCTIONS]
        steps.append(s)
    return steps


@router.get("/api/directions")
def get_directions(
    origin: str = Query(..., description="lat,lng of the start point"),
    destination: str = Query(..., description="lat,lng of the end point"),
    mode: TravelMode = Query(TravelMode.transit, description="Travel mode"),
):
    """
    Proxy Google Directions and return trimmed routing data.

    Returns: {distance_m, duration_s, polyline, mode}
    Caches results in Redis for 1 hour.
    """
    api_key = os.environ.get("GOOGLE_MAPS_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Maps API key not configured")

    cache_key = _cache_key(origin, destination, str(mode))
    r = get_redis()

    # ── Cache hit ─────────────────────────────────────────────────────────────
    cached = r.get(cache_key)
    if cached:
        log.debug("Directions cache hit: %s", cache_key)
        return json.loads(cached)

    # ── Upstream call ─────────────────────────────────────────────────────────
    params = {
        "origin": origin,
        "destination": destination,
        "mode": str(mode),
        "key": api_key,
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(DIRECTIONS_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.exception("Directions API request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Directions API unavailable") from exc

    data = resp.json()
    status = data.get("status")

    if status == "ZERO_RESULTS":
        raise HTTPException(
            status_code=404,
            detail=f"No {mode} route found between the given points",
        )

    if status != "OK":
        log.error("Directions API error status: %s", status)
        raise HTTPException(status_code=502, detail=f"Directions API error: {status}")

    # ── Trim response ─────────────────────────────────────────────────────────
    try:
        route = data["routes"][0]
        leg = route["legs"][0]
        result = {
            "mode": str(mode),
            "distance_m": leg["distance"]["value"],
            "duration_s": leg["duration"]["value"],
            "polyline": route["overview_polyline"]["points"],
            "steps": _extract_steps(leg),
        }
    except (KeyError, IndexError) as exc:
        log.exception("Unexpected Directions API response shape: %s", exc)
        raise HTTPException(status_code=502, detail="Unexpected Directions API response") from exc

    # ── Cache and return ──────────────────────────────────────────────────────
    r.setex(cache_key, CACHE_TTL, json.dumps(result))
    log.debug("Directions cached for %ds: %s→%s [%s]", CACHE_TTL, origin, destination, mode)
    return result
