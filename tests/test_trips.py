"""
Trip/stop CRUD — /api/trips. No dedicated coverage existed for this router
before; added alongside the stops/reorder deadlock-ordering fix (see
app/routers/trips.py's reorder_stops) so that fix has a regression test
and this router isn't entirely untested going forward.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.models.trip import Leg, Stop, Trip  # noqa: E402
from app.models.venue import Venue  # noqa: E402


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Venue.__table__, Trip.__table__, Stop.__table__, Leg.__table__])
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}), patch(
        "app.main._wait_for_db", return_value=None
    ):
        from app.main import app

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


def _make_trip_with_stops(client, n=3):
    trip = client.post("/api/trips", json={"name": "Test Trip"}).json()
    stop_ids = []
    for i in range(n):
        resp = client.post(
            f"/api/trips/{trip['id']}/stops",
            json={"name": f"Stop {i}", "lat": 34.0 + i, "lng": -118.0 - i},
        )
        stop_ids.append(resp.json()["id"])
    return trip["id"], stop_ids


def test_create_trip(client):
    resp = client.post("/api/trips", json={"name": "My Trip"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "My Trip"


def test_add_stop(client):
    trip_id, _ = _make_trip_with_stops(client, n=1)
    resp = client.get(f"/api/trips/{trip_id}")
    assert len(resp.json()["stops"]) == 1


def test_reorder_stops_applies_requested_order(client):
    trip_id, stop_ids = _make_trip_with_stops(client, n=3)
    # Reverse the order, sent in an arbitrary (non-sorted-by-stop_id) sequence.
    body = [
        {"stop_id": stop_ids[2], "order_index": 0},
        {"stop_id": stop_ids[0], "order_index": 2},
        {"stop_id": stop_ids[1], "order_index": 1},
    ]
    resp = client.patch(f"/api/trips/{trip_id}/stops/reorder", json=body)
    assert resp.status_code == 200
    stops = sorted(resp.json()["stops"], key=lambda s: s["order_index"])
    assert [s["id"] for s in stops] == [stop_ids[2], stop_ids[1], stop_ids[0]]


def test_reorder_stops_ignores_unknown_stop_ids(client):
    trip_id, stop_ids = _make_trip_with_stops(client, n=2)
    resp = client.patch(
        f"/api/trips/{trip_id}/stops/reorder",
        json=[{"stop_id": 999999, "order_index": 5}, {"stop_id": stop_ids[0], "order_index": 1}],
    )
    assert resp.status_code == 200


def test_reorder_stops_unknown_trip_404(client):
    resp = client.patch("/api/trips/999999/stops/reorder", json=[])
    assert resp.status_code == 404


def test_delete_stop(client):
    trip_id, stop_ids = _make_trip_with_stops(client, n=2)
    resp = client.delete(f"/api/trips/{trip_id}/stops/{stop_ids[0]}")
    assert resp.status_code == 204
    remaining = client.get(f"/api/trips/{trip_id}").json()["stops"]
    assert len(remaining) == 1
