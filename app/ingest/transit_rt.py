"""
Live Metro transit — GTFS-Realtime vehicle positions via Swiftly.

Why Swiftly: LA Metro's old public JSON RT feeds (api.metro.net/.../
vehicle_positions/all) were retired — they now 404 — and current live vehicle
data is only exposed over a websocket or through Swiftly's GTFS-RT protobuf.
Swiftly is the reliable path, so we proxy it: the SWIFTLY_API_KEY lives only on
the server, and the browser talks to our endpoints, never Swiftly.

Feeds (one per agency), protobuf:
    https://api.goswift.ly/real-time/{agency}/gtfs-rt-vehicle-positions
    header  Authorization: <SWIFTLY_API_KEY>
Agencies for LA Metro: "lametro" (bus) + "lametro-rail" (rail).

Graceful by design: with no key configured (or a feed down) every function
returns a "not configured / scheduled" shape instead of raising, so the app
falls back to Google's scheduled times and never shows a broken "live" badge.

Cache-first: the merged vehicle list is cached in Redis for a short TTL, so each
upstream feed is polled at most once per TTL no matter how many users look.

NOTE: this delivers live *vehicle positions* (is the line running, and where).
True per-stop delay / next-arrival needs the GTFS *static* schedule loaded to
map a boarding stop → stop_id (FR-G1); that's the documented follow-on.
"""

import json
import logging
import os
import re

import httpx
from google.transit import gtfs_realtime_pb2

from app.cache import get_redis

log = logging.getLogger(__name__)

CACHE_KEY = "transit_rt:vehicles"
CACHE_TTL = 20  # seconds — Metro vehicle positions update roughly this often

_SWIFTLY_URL = "https://api.goswift.ly/real-time/{agency}/gtfs-rt-vehicle-positions"
_DEFAULT_AGENCIES = "lametro,lametro-rail"

# Metro rail line letter → GTFS route_id prefix.  Google labels rail lines by
# letter ("A Line", "E Line"); the RT feed keys them by numeric route_id.
_RAIL_LINE_TO_ROUTE = {
    "A": "801", "B": "802", "C": "803", "E": "804",
    "D": "805", "L": "806", "K": "807",
}


def api_key() -> str | None:
    return os.environ.get("SWIFTLY_API_KEY")


def is_configured() -> bool:
    return bool(api_key())


def _agencies() -> list[str]:
    raw = os.environ.get("SWIFTLY_AGENCIES") or _DEFAULT_AGENCIES
    return [a.strip() for a in raw.split(",") if a.strip()]


# ── Pure parsing / matching (no network) ──────────────────────────────────────

def parse_feed(raw: bytes, agency: str) -> list[dict]:
    """Parse a GTFS-RT VehiclePositions protobuf into normalized dicts."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(raw)
    out: list[dict] = []
    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        pos = v.position
        out.append({
            "agency": agency,
            "vehicle_id": v.vehicle.id or entity.id,
            "trip_id": v.trip.trip_id or None,
            "route_id": v.trip.route_id or None,
            "lat": pos.latitude if v.HasField("position") else None,
            "lng": pos.longitude if v.HasField("position") else None,
            "bearing": pos.bearing if v.HasField("position") else None,
            "timestamp": v.timestamp or None,
        })
    return out


def _norm_route_id(route_id: str | None) -> str:
    """Strip any suffix so '801-13149' and '801' compare equal."""
    if not route_id:
        return ""
    return route_id.split("-", 1)[0].strip().upper()


def line_targets(line_ref: str | None) -> set[str]:
    """
    Turn a Google transit line label into the RT route_id(s) it maps to.

    "A Line" / "Metro E Line" → rail route code; "720" → the bus route number.
    """
    if not line_ref:
        return set()
    text = line_ref.strip().upper()
    # Rail: a single letter followed by "LINE" (e.g. "A LINE", "METRO E LINE").
    m = re.search(r"\b([A-K])\s*LINE\b", text)
    if m and m.group(1) in _RAIL_LINE_TO_ROUTE:
        return {_RAIL_LINE_TO_ROUTE[m.group(1)]}
    # Bus: a bare route number.
    m = re.search(r"\b(\d{1,3})\b", text)
    if m:
        return {m.group(1)}
    return set()


def _route_matches(route_id: str | None, targets: set[str]) -> bool:
    norm = _norm_route_id(route_id)
    return any(norm == t or norm.startswith(t) for t in targets)


# ── Network + cache ───────────────────────────────────────────────────────────

def _fetch_agency(client: httpx.Client, agency: str, key: str) -> list[dict]:
    url = _SWIFTLY_URL.format(agency=agency)
    resp = client.get(url, headers={"Authorization": key})
    resp.raise_for_status()
    return parse_feed(resp.content, agency)


def fetch_vehicles() -> dict:
    """
    Fetch + merge live vehicles across agencies, cache, and return.

    Never raises for upstream/config problems — returns a shape carrying
    `configured` and per-agency `errors` so callers can degrade gracefully.
    """
    key = api_key()
    if not key:
        return {"configured": False, "source": "unconfigured", "count": 0, "vehicles": [], "errors": {}}

    vehicles: list[dict] = []
    errors: dict[str, str] = {}
    with httpx.Client(timeout=8) as client:
        for agency in _agencies():
            try:
                vehicles.extend(_fetch_agency(client, agency, key))
            except Exception as exc:  # noqa: BLE001 — one agency down ≠ fail all
                log.warning("Swiftly fetch failed for %s: %s", agency, exc)
                errors[agency] = str(exc)

    r = get_redis()
    r.setex(CACHE_KEY, CACHE_TTL, json.dumps(vehicles))
    return {"configured": True, "source": "live", "count": len(vehicles), "vehicles": vehicles, "errors": errors}


def get_vehicles() -> dict:
    """Cache-first accessor for the live vehicle list."""
    if not is_configured():
        return {"configured": False, "source": "unconfigured", "count": 0, "vehicles": [], "errors": {}}
    r = get_redis()
    raw = r.get(CACHE_KEY)
    if raw is not None:
        vehicles = json.loads(raw)
        return {"configured": True, "source": "cache", "count": len(vehicles), "vehicles": vehicles, "errors": {}}
    return fetch_vehicles()


def live_status_for_line(line_ref: str | None) -> dict:
    """
    Live running status for a transit line label from Google directions.

    Returns a stable shape: {configured, status, live, vehicles_running, line,
    targets}.  status ∈ {"live", "no_service", "scheduled"} — "scheduled" means
    we have no live feed (unconfigured/down) so the caller should show schedule.
    """
    targets = line_targets(line_ref)
    if not is_configured():
        return {"configured": False, "status": "scheduled", "live": None,
                "vehicles_running": 0, "line": line_ref, "targets": sorted(targets)}

    data = get_vehicles()
    count = sum(1 for v in data["vehicles"] if _route_matches(v.get("route_id"), targets)) if targets else 0

    if count > 0:
        status, live = "live", True
    elif data.get("errors"):
        # A feed errored (e.g. the rail agency 403s) — we can't distinguish
        # "not running" from "not fetched", so fall back to scheduled honestly.
        status, live = "scheduled", None
    else:
        # Full coverage, no match → genuinely nothing running on this line.
        status, live = "no_service", False

    return {
        "configured": True,
        "status": status,
        "live": live,
        "vehicles_running": count,
        "line": line_ref,
        "targets": sorted(targets),
    }
