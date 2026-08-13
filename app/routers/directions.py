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
from fastapi import APIRouter, Depends, HTTPException, Query

from app.cache import get_redis
from app.rate_limit import DIRECTIONS_RATE_LIMIT, rate_limit

log = logging.getLogger(__name__)
router = APIRouter(tags=["directions"])

DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
CACHE_TTL = 3600  # 1 hour — venue-to-venue routes are stable


class TravelMode(StrEnum):
    driving = "driving"
    transit = "transit"
    walking = "walking"
    bicycling = "bicycling"


# App locale codes (frontend/lib/i18n.ts SUPPORTED_LANGUAGES) → Google
# Directions `language` codes. Google uses zh-CN for Simplified Chinese, not
# our app's zh-Hans — everything else matches 1:1. Unknown/missing codes fall
# back to English.
_GOOGLE_LANGUAGE = {"en": "en", "es": "es", "fr": "fr", "zh-Hans": "zh-CN"}
DEFAULT_LANGUAGE = "en"


def _normalize_language(language: str | None) -> str:
    """App locale code if supported, else English — never forward an
    unrecognized code to the cache key or Google."""
    return language if language in _GOOGLE_LANGUAGE else DEFAULT_LANGUAGE


# Departure-time bucket for transit cache keys.  Transit routes DO depend on
# when you leave, so the cache key must include it — otherwise the engine would
# silently serve a route computed for a different time.  Bucketing to 5-minute
# windows keeps hit rates sane while staying time-aware.
DEPARTURE_BUCKET_S = 300


class DirectionsError(Exception):
    """Upstream/config failure with an HTTP status hint for the route layer."""

    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _api_key() -> str | None:
    return os.environ.get("GOOGLE_MAPS_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")


def _cache_key(
    origin: str, destination: str, mode: str, language: str, departure_bucket: int | None = None,
) -> str:
    # Round coordinates to 5 dp to collapse trivially different floats.
    def _norm(coord: str) -> str:
        parts = coord.split(",")
        if len(parts) == 2:
            try:
                return f"{float(parts[0]):.5f},{float(parts[1]):.5f}"
            except ValueError:
                pass
        return coord

    # language is always folded in (unlike the departure bucket) so English
    # and Spanish requests for the same route never collide — deploying this
    # changed the key shape, so old `dir:*` entries were flushed once.
    raw = f"directions:{_norm(origin)}:{_norm(destination)}:{mode}:{language}"
    # Only transit passes a departure bucket; other modes keep their old keys
    # (no cache churn) since walking/driving/bicycling don't depend on time.
    if departure_bucket is not None:
        raw += f":dep{departure_bucket}"
    # Hash to cap key length and avoid special characters.
    return "dir:" + hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 — not crypto


def fetch_directions(
    origin: str,
    destination: str,
    mode: str,
    departure_time: int | None = None,
    language: str | None = None,
) -> dict | None:
    """
    Core Directions fetch — cache-first, returns the trimmed result dict.

    Returns None when Google reports ZERO_RESULTS (no route of this mode), so
    callers (the route engine) can treat "no route" as "candidate infeasible"
    rather than an error.  Raises DirectionsError for config/upstream failures.

    departure_time (unix seconds) is honoured for transit only and is folded
    into the cache key via a 5-minute bucket.

    language is an app locale code (see frontend/lib/i18n.ts); an unsupported
    or missing code falls back to English before hitting the cache or Google,
    so turn-by-turn `steps[].instruction` come back localized.
    """
    api_key = _api_key()
    if not api_key:
        raise DirectionsError("Maps API key not configured", status_code=500)

    language = _normalize_language(language)
    is_transit = mode == "transit"
    bucket = None
    if is_transit and departure_time:
        bucket = departure_time - (departure_time % DEPARTURE_BUCKET_S)

    cache_key = _cache_key(origin, destination, mode, language, bucket)
    r = get_redis()
    cached = r.get(cache_key)
    if cached:
        log.debug("Directions cache hit: %s", cache_key)
        return json.loads(cached)

    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "language": _GOOGLE_LANGUAGE[language],
        "key": api_key,
    }
    if is_transit and departure_time:
        params["departure_time"] = int(departure_time)

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(DIRECTIONS_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.exception("Directions API request failed: %s", exc)
        raise DirectionsError("Directions API unavailable", status_code=502) from exc

    data = resp.json()
    status = data.get("status")

    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        log.error("Directions API error status: %s", status)
        raise DirectionsError(f"Directions API error: {status}", status_code=502)

    try:
        route = data["routes"][0]
        leg = route["legs"][0]
        result = {
            "mode": mode,
            "distance_m": leg["distance"]["value"],
            "duration_s": leg["duration"]["value"],
            "polyline": route["overview_polyline"]["points"],
            "steps": _extract_steps(leg, language),
        }
    except (KeyError, IndexError) as exc:
        log.exception("Unexpected Directions API response shape: %s", exc)
        raise DirectionsError("Unexpected Directions API response", status_code=502) from exc

    r.setex(cache_key, CACHE_TTL, json.dumps(result))
    log.debug("Directions cached for %ds: %s→%s [%s/%s]", CACHE_TTL, origin, destination, mode, language)
    return result


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


def _clean_instruction(instruction: str, maneuver: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Make Google navigation instructions friendlier for tourists.

    These patterns ("Head northwest…", "toward X") match Google's English
    phrasing only — they're a no-op on other languages' instructions, so we
    skip them outright rather than leave dead regex running on non-English
    text.
    """
    if not instruction:
        return instruction
    if language != "en":
        return instruction.strip()
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


def _extract_steps(leg: dict, language: str = DEFAULT_LANGUAGE) -> list[dict]:
    steps = []
    for step in leg.get("steps", []):
        raw_instruction = _strip_html(step.get("html_instructions", ""))
        # Strip administrative notes appended by Google as inline divs (e.g.
        # "Restricted usage road"). _SKIP_INSTRUCTIONS is English text, so
        # this (like _clean_instruction) only trims something on English
        # responses — on other languages the note passes through untouched.
        if language == "en":
            raw_instruction = _SKIP_PATTERN.sub("", raw_instruction).strip()
        maneuver = step.get("maneuver", "") or ""

        # Skip steps whose entire content is an administrative note
        if language == "en" and raw_instruction.lower().rstrip(".") in _SKIP_INSTRUCTIONS:
            continue

        instruction = _clean_instruction(raw_instruction, maneuver, language)
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
                _clean_instruction(
                    _strip_html(ss.get("html_instructions", "")), ss.get("maneuver", "") or "", language,
                )
                for ss in step["steps"]
            ]
            s["sub_steps"] = [
                x for x in sub if x and (language != "en" or x.lower().rstrip(".") not in _SKIP_INSTRUCTIONS)
            ]
        steps.append(s)
    return steps


@router.get("/api/directions", dependencies=[Depends(rate_limit("directions", DIRECTIONS_RATE_LIMIT, 60))])
def get_directions(
    origin: str = Query(..., description="lat,lng of the start point"),
    destination: str = Query(..., description="lat,lng of the end point"),
    mode: TravelMode = Query(TravelMode.transit, description="Travel mode"),
    language: str | None = Query(None, description="App locale code (en/es/fr/zh-Hans); unsupported falls back to en"),
):
    """
    Proxy Google Directions and return trimmed routing data.

    Rate-limited (see app.rate_limit) — this calls the real, paid Google
    Directions API on a cache miss, so an unbounded client could otherwise
    drive up billing directly through our own proxy.

    Returns: {mode, distance_m, duration_s, polyline, steps}
    Caches results in Redis for 1 hour, keyed per language too.
    """
    try:
        result = fetch_directions(origin, destination, str(mode), language=language)
    except DirectionsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {mode} route found between the given points",
        )
    return result
