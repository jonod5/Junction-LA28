"""
Live transit (Swiftly GTFS-RT) — protobuf parsing, line matching, and the
graceful-degradation contract that keeps the app honest when no key is set.

A real GTFS-RT FeedMessage is built and serialized in-process, so parsing is
exercised against genuine protobuf bytes with no network.
"""

import pytest
from google.transit import gtfs_realtime_pb2

from app.ingest import transit_rt


def _feed(vehicles: list[dict]) -> bytes:
    """Build a serialized VehiclePositions FeedMessage from simple dicts."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    for i, v in enumerate(vehicles):
        ent = feed.entity.add()
        ent.id = f"e{i}"
        veh = ent.vehicle
        veh.vehicle.id = v.get("vehicle_id", f"v{i}")
        veh.trip.trip_id = v.get("trip_id", "")
        veh.trip.route_id = v.get("route_id", "")
        veh.position.latitude = v.get("lat", 34.0)
        veh.position.longitude = v.get("lng", -118.0)
    return feed.SerializeToString()


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_parse_feed_extracts_vehicles():
    raw = _feed([
        {"vehicle_id": "1001", "route_id": "801", "lat": 34.05, "lng": -118.23},
        {"vehicle_id": "1002", "route_id": "720", "lat": 34.06, "lng": -118.30},
    ])
    out = transit_rt.parse_feed(raw, "lametro-rail")
    assert [v["route_id"] for v in out] == ["801", "720"]
    assert out[0]["agency"] == "lametro-rail"
    assert out[0]["lat"] == pytest.approx(34.05, abs=1e-4)


def test_parse_feed_ignores_non_vehicle_entities():
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    ent = feed.entity.add()
    ent.id = "alert-only"
    ent.alert.header_text.translation.add().text = "delay"
    assert transit_rt.parse_feed(feed.SerializeToString(), "lametro") == []


# ── Line label → route target matching ────────────────────────────────────────

def test_line_targets_rail_letters():
    assert transit_rt.line_targets("A Line") == {"801"}
    assert transit_rt.line_targets("Metro E Line") == {"804"}
    assert transit_rt.line_targets("K Line") == {"807"}


def test_line_targets_bus_number():
    assert transit_rt.line_targets("720") == {"720"}
    assert transit_rt.line_targets("Metro 204") == {"204"}


def test_line_targets_unknown():
    assert transit_rt.line_targets("") == set()
    assert transit_rt.line_targets(None) == set()


def test_route_matches_strips_suffix():
    assert transit_rt._route_matches("801-13149", {"801"}) is True
    assert transit_rt._route_matches("802", {"801"}) is False


# ── Graceful degradation (no key configured) ──────────────────────────────────

def test_unconfigured_returns_scheduled(monkeypatch):
    monkeypatch.delenv("SWIFTLY_API_KEY", raising=False)
    assert transit_rt.is_configured() is False

    v = transit_rt.get_vehicles()
    assert v == {"configured": False, "source": "unconfigured", "count": 0, "vehicles": [], "errors": {}}

    status = transit_rt.live_status_for_line("A Line")
    assert status["configured"] is False
    assert status["status"] == "scheduled"
    assert status["live"] is None


# ── Live status with a configured key (cache stubbed) ──────────────────────────

def test_live_status_counts_matching_vehicles(monkeypatch):
    monkeypatch.setenv("SWIFTLY_API_KEY", "TEST")
    monkeypatch.setattr(transit_rt, "get_vehicles", lambda: {
        "configured": True, "source": "cache", "count": 3, "errors": {},
        "vehicles": [
            {"route_id": "801-13149"}, {"route_id": "801"}, {"route_id": "720"},
        ],
    })
    status = transit_rt.live_status_for_line("A Line")
    assert status["live"] is True
    assert status["vehicles_running"] == 2      # two 801s, not the 720
    assert status["status"] == "live"


def test_live_status_no_vehicles_is_no_service(monkeypatch):
    monkeypatch.setenv("SWIFTLY_API_KEY", "TEST")
    monkeypatch.setattr(transit_rt, "get_vehicles", lambda: {
        "configured": True, "source": "cache", "count": 1, "errors": {},
        "vehicles": [{"route_id": "999"}],
    })
    status = transit_rt.live_status_for_line("A Line")
    assert status["live"] is False
    assert status["status"] == "no_service"


def test_live_status_feed_error_falls_back_to_scheduled(monkeypatch):
    monkeypatch.setenv("SWIFTLY_API_KEY", "TEST")
    monkeypatch.setattr(transit_rt, "get_vehicles", lambda: {
        "configured": True, "source": "live", "count": 0,
        "vehicles": [], "errors": {"lametro": "boom"},
    })
    status = transit_rt.live_status_for_line("A Line")
    assert status["status"] == "scheduled"
    assert status["live"] is None
