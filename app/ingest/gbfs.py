"""
GBFS ingestion — live shared micromobility (scooters, bikes, e-bikes).

GBFS (General Bikeshare Feed Specification) is the open standard the operators
publish under the GBFS Data License — royalty-free, attribution required.  We
proxy it through the backend so:
  • no vendor keys or third-party calls ever reach the browser, and
  • we hit each public feed at most once per its TTL (never hammering them).

Providers (LA public feeds, no auth).  Each exposes a root `gbfs.json` that
lists the actual per-feed URLs; we discover them rather than hard-coding paths,
because operators version their feed trees differently:
  • Bird             — free-floating scooters
  • Spin             — free-floating scooters / e-bikes
  • Metro Bike Share — docked bikes (stations)

Design choices mirror gtfs_rt.py:
  • Cache each feed's raw payload in Redis under gbfs:{provider}:{feed} with a
    TTL = min(feed ttl, 60s); every request reads cache-first.
  • One provider (or one feed) failing never sinks the others — errors are
    collected and returned in metadata so the UI can degrade gracefully and
    keep showing the hand-collected static zones as a labeled fallback.
  • Normalisation is pure (no network) so it is unit-testable in isolation.
"""

import json
import logging
import math
import os

import httpx

from app.cache import get_redis

log = logging.getLogger(__name__)

# Cap every feed's TTL — even if a provider advertises a longer ttl we refresh
# at least once a minute so availability never goes badly stale on the map.
MAX_TTL = 60

# GBFS Data License — surfaced in endpoint metadata.
GBFS_LICENSE = "https://github.com/MobilityData/gbfs/blob/master/gbfs.md"
ATTRIBUTION = (
    "Live micromobility data via GBFS feeds (Bird, Spin, Metro Bike Share), "
    "used under the GBFS Data License — royalty-free with attribution."
)

# provider_key → (display name, root gbfs.json URL, default vehicle type).
# Default type is a fallback for feeds that don't publish vehicle_types.json.
_DEFAULT_PROVIDERS: dict[str, tuple[str, str, str]] = {
    "bird": ("Bird", "https://mds.bird.co/gbfs/v2/public/los-angeles/gbfs.json", "scooter"),
    "spin": ("Spin", "https://gbfs.spin.pm/api/gbfs/v2_3/los_angeles/gbfs.json", "scooter"),
    "metro-bike-share": ("Metro Bike Share", "https://gbfs.bcycle.com/bcycle_lametro/gbfs.json", "bike"),
}


def providers() -> dict[str, tuple[str, str, str]]:
    """
    Provider config, overridable via env without a code change.

    GBFS_PROVIDER_ROOTS = "bird=<url>,spin=<url>,metro-bike-share=<url>"
    Only overrides the root URL; display name / default type come from defaults.
    """
    override = os.environ.get("GBFS_PROVIDER_ROOTS", "").strip()
    if not override:
        return _DEFAULT_PROVIDERS
    result = {k: v for k, v in _DEFAULT_PROVIDERS.items()}
    for pair in override.split(","):
        if "=" not in pair:
            continue
        key, url = pair.split("=", 1)
        key, url = key.strip(), url.strip()
        name, _old, vtype = _DEFAULT_PROVIDERS.get(key, (key.title(), "", "scooter"))
        result[key] = (name, url, vtype)
    return result


# ── Pure helpers (no network) ─────────────────────────────────────────────────

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two lat/lng points."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def discover_feeds(root_data: dict) -> dict[str, str]:
    """
    Parse a root gbfs.json into {feed_name: url}.

    Handles both shapes seen in the wild:
      { "data": { "<lang>": { "feeds": [...] } } }   (language-keyed)
      { "data": { "feeds": [...] } }                 (no language key)
    """
    data = root_data.get("data") or {}
    feeds = data.get("feeds")
    if feeds is None:
        # Language-keyed: take the first language block that has feeds.
        for block in data.values():
            if isinstance(block, dict) and block.get("feeds"):
                feeds = block["feeds"]
                break
    result: dict[str, str] = {}
    for f in feeds or []:
        name, url = f.get("name"), f.get("url")
        if name and url:
            result[name] = url
    return result


def ttl_from(feed_data: dict, cap: int = MAX_TTL) -> int:
    """TTL in seconds for a feed, honouring its `ttl` field but capped."""
    raw = feed_data.get("ttl")
    try:
        ttl = int(raw)
    except (TypeError, ValueError):
        ttl = cap
    return max(1, min(ttl, cap))


def _vehicle_type_map(vehicle_types_data: dict | None) -> dict[str, str]:
    """Map vehicle_type_id → normalized type (bike|ebike|scooter) if published."""
    result: dict[str, str] = {}
    if not vehicle_types_data:
        return result
    for vt in (vehicle_types_data.get("data") or {}).get("vehicle_types", []):
        vid = vt.get("vehicle_type_id")
        if not vid:
            continue
        form = (vt.get("form_factor") or "").lower()
        prop = (vt.get("propulsion_type") or "").lower()
        if form == "scooter":
            result[vid] = "scooter"
        elif form == "bicycle":
            result[vid] = "bike" if prop in ("human", "") else "ebike"
        else:
            result[vid] = "scooter"
    return result


def normalize_free_bikes(
    feed_data: dict, provider_key: str, default_type: str, vehicle_types_data: dict | None = None
) -> list[dict]:
    """Normalise free_bike_status bikes into common vehicle dicts."""
    type_map = _vehicle_type_map(vehicle_types_data)
    out: list[dict] = []
    for b in (feed_data.get("data") or {}).get("bikes", []):
        # Skip vehicles that aren't actually rentable right now.
        if b.get("is_reserved") or b.get("is_disabled"):
            continue
        lat = b.get("lat")
        lng = b.get("lon")
        if lat is None or lng is None:
            continue
        vtype = type_map.get(b.get("vehicle_type_id"), default_type)
        out.append({
            "provider": provider_key,
            "kind": "vehicle",
            "vehicle_type": vtype,
            "lat": lat,
            "lng": lng,
            "id": b.get("bike_id") or b.get("id"),
        })
    return out


def normalize_stations(
    info_data: dict, status_data: dict, provider_key: str, default_type: str
) -> list[dict]:
    """Join station_information + station_status into common station dicts."""
    status_by_id: dict[str, dict] = {
        s.get("station_id"): s
        for s in (status_data.get("data") or {}).get("stations", [])
    }
    out: list[dict] = []
    for info in (info_data.get("data") or {}).get("stations", []):
        sid = info.get("station_id")
        lat, lng = info.get("lat"), info.get("lon")
        if lat is None or lng is None:
            continue
        status = status_by_id.get(sid, {})
        # Only surface stations that are installed and renting.
        if status and (status.get("is_renting") == 0 or status.get("is_installed") == 0):
            continue
        num_bikes = status.get("num_bikes_available")
        num_ebikes = status.get("num_ebikes_available")
        out.append({
            "provider": provider_key,
            "kind": "station",
            "vehicle_type": default_type,
            "lat": lat,
            "lng": lng,
            "id": sid,
            "name": info.get("name"),
            "num_bikes_available": num_bikes,
            "num_ebikes_available": num_ebikes,
            "num_docks_available": status.get("num_docks_available"),
        })
    return out


def parse_pricing(pricing_data: dict) -> list[dict]:
    """Extract system_pricing_plans into a compact, labeled list."""
    out: list[dict] = []
    for p in (pricing_data.get("data") or {}).get("plans", []):
        out.append({
            "plan_id": p.get("plan_id"),
            "name": p.get("name"),
            "currency": p.get("currency"),
            "price": p.get("price"),          # unlock / base price
            "is_taxable": p.get("is_taxable"),
            "description": p.get("description"),
            "per_min_pricing": p.get("per_min_pricing"),  # [{start, rate, interval}]
        })
    return out


# ── Network + cache ───────────────────────────────────────────────────────────

def _fetch_json(client: httpx.Client, url: str) -> dict:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.json()


def _cached_feed(client: httpx.Client, provider_key: str, feed_name: str, url: str) -> dict:
    """
    Return a feed's raw JSON, cache-first.

    On a miss we fetch upstream once and cache under the feed's own TTL, so the
    public feed is hit at most once per TTL no matter how many users query.
    """
    r = get_redis()
    key = f"gbfs:{provider_key}:{feed_name}"
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)
    data = _fetch_json(client, url)
    r.setex(key, ttl_from(data), json.dumps(data))
    return data


def get_provider_snapshot(provider_key: str) -> dict:
    """
    Fetch + normalise one provider's live inventory, cache-first per feed.

    Returns {vehicles, stations, pricing, errors}.  Never raises for upstream
    failures — they land in `errors` so the caller can degrade gracefully.
    """
    conf = providers().get(provider_key)
    if not conf:
        return {"vehicles": [], "stations": [], "pricing": [], "errors": ["unknown provider"]}
    name, root_url, default_type = conf

    vehicles: list[dict] = []
    stations: list[dict] = []
    pricing: list[dict] = []
    errors: list[str] = []

    try:
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            root = _cached_feed(client, provider_key, "root", root_url)
            feeds = discover_feeds(root)

            vehicle_types_data = None
            if "vehicle_types" in feeds:
                try:
                    vehicle_types_data = _cached_feed(client, provider_key, "vehicle_types", feeds["vehicle_types"])
                except httpx.HTTPError as exc:
                    errors.append(f"vehicle_types: {exc}")

            if "free_bike_status" in feeds:
                try:
                    fb = _cached_feed(client, provider_key, "free_bike_status", feeds["free_bike_status"])
                    vehicles = normalize_free_bikes(fb, provider_key, default_type, vehicle_types_data)
                except httpx.HTTPError as exc:
                    errors.append(f"free_bike_status: {exc}")

            if "station_information" in feeds and "station_status" in feeds:
                try:
                    info = _cached_feed(client, provider_key, "station_information", feeds["station_information"])
                    status = _cached_feed(client, provider_key, "station_status", feeds["station_status"])
                    stations = normalize_stations(info, status, provider_key, default_type)
                except httpx.HTTPError as exc:
                    errors.append(f"stations: {exc}")

            if "system_pricing_plans" in feeds:
                try:
                    pp = _cached_feed(client, provider_key, "system_pricing_plans", feeds["system_pricing_plans"])
                    pricing = parse_pricing(pp)
                except httpx.HTTPError as exc:
                    errors.append(f"system_pricing_plans: {exc}")
    except httpx.HTTPError as exc:
        # Root discovery failed — whole provider is unavailable this cycle.
        log.warning("GBFS provider %s unavailable: %s", provider_key, exc)
        errors.append(f"root: {exc}")

    return {"vehicles": vehicles, "stations": stations, "pricing": pricing, "errors": errors}


def get_nearby(lat: float, lng: float, radius_m: float) -> dict:
    """
    Aggregate all providers and return items within radius_m of (lat, lng).

    Each item carries a `distance_m`.  Provider-level failures are reported in
    `errors` (per provider) so the endpoint can note degraded feeds without
    failing the whole response.
    """
    items: list[dict] = []
    pricing_by_provider: dict[str, list[dict]] = {}
    errors: dict[str, list[str]] = {}

    for provider_key in providers():
        snap = get_provider_snapshot(provider_key)
        if snap["errors"]:
            errors[provider_key] = snap["errors"]
        if snap["pricing"]:
            pricing_by_provider[provider_key] = snap["pricing"]

        for item in snap["vehicles"] + snap["stations"]:
            d = haversine_m(lat, lng, item["lat"], item["lng"])
            if d <= radius_m:
                items.append({**item, "distance_m": round(d, 1)})

    items.sort(key=lambda x: x["distance_m"])
    return {"items": items, "pricing": pricing_by_provider, "errors": errors}
