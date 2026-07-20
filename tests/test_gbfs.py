"""
GBFS ingestion — pure parsing + cache-first / graceful-degradation behaviour.

Network and Redis are both faked so these run offline in CI.
"""

import json

import httpx
import pytest

from app.ingest import gbfs


# ── Pure helpers ──────────────────────────────────────────────────────────────

def test_discover_feeds_language_keyed():
    root = {"data": {"en": {"feeds": [
        {"name": "free_bike_status", "url": "https://x/fb.json"},
        {"name": "system_pricing_plans", "url": "https://x/pp.json"},
    ]}}}
    feeds = gbfs.discover_feeds(root)
    assert feeds == {
        "free_bike_status": "https://x/fb.json",
        "system_pricing_plans": "https://x/pp.json",
    }


def test_discover_feeds_no_language_key():
    root = {"data": {"feeds": [{"name": "station_information", "url": "https://x/si.json"}]}}
    assert gbfs.discover_feeds(root) == {"station_information": "https://x/si.json"}


def test_ttl_is_capped_at_60():
    assert gbfs.ttl_from({"ttl": 3600}) == 60
    assert gbfs.ttl_from({"ttl": 15}) == 15
    assert gbfs.ttl_from({}) == 60           # missing → cap
    assert gbfs.ttl_from({"ttl": 0}) == 1    # floor at 1


def test_haversine_known_distance():
    # ~111 km per degree of latitude near the equator/mid-latitudes.
    d = gbfs.haversine_m(34.0, -118.0, 34.05, -118.0)
    assert 5000 < d < 6000  # ~5.5 km


def test_normalize_free_bikes_skips_unavailable_and_tags_type():
    data = {"data": {"bikes": [
        {"bike_id": "b1", "lat": 34.0, "lon": -118.0},
        {"bike_id": "b2", "lat": 34.0, "lon": -118.0, "is_disabled": True},
        {"bike_id": "b3", "lat": 34.0, "lon": -118.0, "is_reserved": True},
        {"bike_id": "b4", "lon": -118.0},  # missing lat → dropped
    ]}}
    out = gbfs.normalize_free_bikes(data, "bird", "scooter")
    assert [b["id"] for b in out] == ["b1"]
    assert out[0]["vehicle_type"] == "scooter"
    assert out[0]["provider"] == "bird"


def test_normalize_free_bikes_uses_vehicle_types_map():
    data = {"data": {"bikes": [{"bike_id": "e1", "lat": 34.0, "lon": -118.0, "vehicle_type_id": "vt_ebike"}]}}
    vt = {"data": {"vehicle_types": [
        {"vehicle_type_id": "vt_ebike", "form_factor": "bicycle", "propulsion_type": "electric_assist"},
    ]}}
    out = gbfs.normalize_free_bikes(data, "spin", "scooter", vt)
    assert out[0]["vehicle_type"] == "ebike"


def test_normalize_stations_joins_and_filters():
    info = {"data": {"stations": [
        {"station_id": "s1", "name": "A", "lat": 34.0, "lon": -118.0},
        {"station_id": "s2", "name": "B", "lat": 34.0, "lon": -118.0},
    ]}}
    status = {"data": {"stations": [
        {"station_id": "s1", "num_bikes_available": 3, "num_docks_available": 5, "is_renting": 1, "is_installed": 1},
        {"station_id": "s2", "num_bikes_available": 0, "is_renting": 0, "is_installed": 1},  # not renting → drop
    ]}}
    out = gbfs.normalize_stations(info, status, "metro-bike-share", "bike")
    assert [s["id"] for s in out] == ["s1"]
    assert out[0]["num_bikes_available"] == 3
    assert out[0]["kind"] == "station"


def test_parse_pricing():
    data = {"data": {"plans": [
        {"plan_id": "p1", "name": "Std", "currency": "USD", "price": 1.0,
         "per_min_pricing": [{"start": 0, "rate": 0.39, "interval": 1}]},
    ]}}
    plans = gbfs.parse_pricing(data)
    assert plans[0]["price"] == 1.0
    assert plans[0]["per_min_pricing"][0]["rate"] == 0.39


# ── Cache-first + graceful degradation ────────────────────────────────────────

class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_calls = 0

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, val):
        self.set_calls += 1
        self.store[key] = val


ROOT = {"data": {"en": {"feeds": [
    {"name": "free_bike_status", "url": "u://fb"},
    {"name": "system_pricing_plans", "url": "u://pp"},
]}}, "ttl": 60}
FB = {"data": {"bikes": [
    {"bike_id": "b1", "lat": 34.000, "lon": -118.000},
    {"bike_id": "b2", "lat": 34.050, "lon": -118.000},  # ~5.5 km away
]}, "ttl": 30}
PP = {"data": {"plans": [{"plan_id": "p1", "name": "Std", "price": 1.0}]}}

FEED_BY_URL = {
    "u://root": ROOT,
    "u://fb": FB,
    "u://pp": PP,
}


@pytest.fixture
def one_provider(monkeypatch):
    """Single fake provider + fake redis + canned feeds (no network)."""
    fake = FakeRedis()
    monkeypatch.setattr(gbfs, "get_redis", lambda: fake)
    monkeypatch.setattr(gbfs, "providers", lambda: {"bird": ("Bird", "u://root", "scooter")})

    fetch_count = {"n": 0}

    def fake_fetch(client, url):
        fetch_count["n"] += 1
        if url not in FEED_BY_URL:
            raise httpx.HTTPError(f"boom {url}")
        return FEED_BY_URL[url]

    monkeypatch.setattr(gbfs, "_fetch_json", fake_fetch)
    return fake, fetch_count


def test_snapshot_normalises_all_feeds(one_provider):
    snap = gbfs.get_provider_snapshot("bird")
    assert [v["id"] for v in snap["vehicles"]] == ["b1", "b2"]
    assert snap["pricing"][0]["plan_id"] == "p1"
    assert snap["errors"] == []


def test_second_call_is_served_from_cache(one_provider):
    _fake, fetch_count = one_provider
    gbfs.get_provider_snapshot("bird")
    first = fetch_count["n"]
    assert first == 3  # root + free_bike_status + pricing
    gbfs.get_provider_snapshot("bird")
    assert fetch_count["n"] == first  # no new upstream hits — cache served


def test_nearby_filters_by_radius(one_provider):
    near = gbfs.get_nearby(34.0, -118.0, 500)
    assert [i["id"] for i in near["items"]] == ["b1"]  # b2 is ~5.5 km out
    assert near["items"][0]["distance_m"] < 1.0


def test_feed_failure_is_isolated(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(gbfs, "get_redis", lambda: fake)
    monkeypatch.setattr(gbfs, "providers", lambda: {"bird": ("Bird", "u://root", "scooter")})

    def fetch_with_bad_pricing(client, url):
        if url == "u://pp":
            raise httpx.HTTPError("pricing down")
        return FEED_BY_URL[url]

    monkeypatch.setattr(gbfs, "_fetch_json", fetch_with_bad_pricing)
    snap = gbfs.get_provider_snapshot("bird")
    # Vehicles still came through; only pricing errored.
    assert [v["id"] for v in snap["vehicles"]] == ["b1", "b2"]
    assert snap["pricing"] == []
    assert any("system_pricing_plans" in e for e in snap["errors"])


def test_root_failure_marks_whole_provider(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(gbfs, "get_redis", lambda: fake)
    monkeypatch.setattr(gbfs, "providers", lambda: {"bird": ("Bird", "u://root", "scooter")})
    monkeypatch.setattr(gbfs, "_fetch_json", lambda c, u: (_ for _ in ()).throw(httpx.HTTPError("root down")))
    snap = gbfs.get_provider_snapshot("bird")
    assert snap["vehicles"] == [] and snap["stations"] == []
    assert any("root" in e for e in snap["errors"])


def test_cache_stores_json_serialisable(one_provider):
    fake, _ = one_provider
    gbfs.get_provider_snapshot("bird")
    # Everything cached must round-trip through json.
    for val in fake.store.values():
        assert json.loads(val) is not None
