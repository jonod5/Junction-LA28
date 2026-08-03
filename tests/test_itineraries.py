"""Saved itinerary CRUD — /api/itineraries.

Uses FastAPI's TestClient with get_db/get_current_user overridden, rather
than direct function calls (the pattern in test_auth.py) — this router has
enough query-param filtering/sorting/pagination surface that exercising it
through real HTTP request parsing is worth the extra fixture setup.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import datetime as dt  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth import get_current_user  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.models.itinerary import Itinerary, ItineraryTag, itinerary_tag_link  # noqa: E402
from app.models.user import User  # noqa: E402

USER_A = User(id="a0000000-0000-0000-0000-000000000001", email="a@example.com")
USER_B = User(id="b0000000-0000-0000-0000-000000000002", email="b@example.com")


@pytest.fixture
def client():
    # StaticPool shares one connection across sessions so the in-memory DB
    # isn't wiped between requests within a test.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        engine, tables=[User.__table__, Itinerary.__table__, ItineraryTag.__table__, itinerary_tag_link]
    )
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    seed = TestSessionLocal()
    seed.add_all([User(id=USER_A.id, email=USER_A.email), User(id=USER_B.id, email=USER_B.email)])
    seed.commit()
    seed.close()

    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}), patch(
        "app.main._wait_for_db", return_value=None
    ):
        from app.main import app

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: USER_A

        with TestClient(app) as c:
            c.app = app
            c.as_user_a = lambda: app.dependency_overrides.__setitem__(get_current_user, lambda: USER_A)
            c.as_user_b = lambda: app.dependency_overrides.__setitem__(get_current_user, lambda: USER_B)
            yield c

        app.dependency_overrides.clear()


SAMPLE_PLAN = {
    "stops": [{"id": 1, "name": "SoFi Stadium", "lat": 33.9535, "lng": -118.339}],
    "legs": {"1-2": {"selected_option": {"id": "opt1", "total_minutes": 20, "total_cost_usd": 5.5}}},
}


def _create(client, **overrides):
    body = {"name": "My Trip", "saved_plan": SAMPLE_PLAN, **overrides}
    return client.post("/api/itineraries", json=body)


# ── Create / get ─────────────────────────────────────────────────────────────

def test_create_and_get_round_trips_snapshot(client):
    resp = _create(client, trip_date="2028-07-15", tags=["Family", "Opening Weekend"])
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "My Trip"
    assert created["trip_date"] == "2028-07-15"
    assert created["saved_plan"] == SAMPLE_PLAN
    assert created["tags"] == ["Family", "Opening Weekend"]
    assert created["is_pinned"] is False

    got = client.get(f"/api/itineraries/{created['id']}")
    assert got.status_code == 200
    assert got.json() == created


def test_create_without_trip_date_or_tags(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["trip_date"] is None
    assert body["tags"] == []


# ── Ownership scoping ────────────────────────────────────────────────────────

def test_list_scoped_to_current_user(client):
    _create(client, name="A's trip")
    client.as_user_b()
    _create(client, name="B's trip")

    resp = client.get("/api/itineraries")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "B's trip"


def test_get_other_users_itinerary_is_404_not_403(client):
    created = _create(client).json()
    client.as_user_b()
    resp = client.get(f"/api/itineraries/{created['id']}")
    assert resp.status_code == 404


def test_update_other_users_itinerary_is_404(client):
    created = _create(client).json()
    client.as_user_b()
    resp = client.patch(f"/api/itineraries/{created['id']}", json={"name": "Hijacked"})
    assert resp.status_code == 404


def test_delete_other_users_itinerary_is_404(client):
    created = _create(client).json()
    client.as_user_b()
    resp = client.delete(f"/api/itineraries/{created['id']}")
    assert resp.status_code == 404
    client.as_user_a()
    assert client.get(f"/api/itineraries/{created['id']}").status_code == 200


def test_delete_owned_itinerary(client):
    created = _create(client).json()
    resp = client.delete(f"/api/itineraries/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/api/itineraries/{created['id']}").status_code == 404


def test_missing_auth_is_401(client):
    del client.app.dependency_overrides[get_current_user]
    resp = client.get("/api/itineraries")
    assert resp.status_code == 401
    client.as_user_a()


# ── Partial update semantics ─────────────────────────────────────────────────

def test_patch_only_touches_provided_fields(client):
    created = _create(client, trip_date="2028-07-15").json()
    resp = client.patch(f"/api/itineraries/{created['id']}", json={"is_pinned": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_pinned"] is True
    assert body["name"] == "My Trip"
    assert body["trip_date"] == "2028-07-15"


def test_patch_can_explicitly_clear_trip_date(client):
    created = _create(client, trip_date="2028-07-15").json()
    resp = client.patch(f"/api/itineraries/{created['id']}", json={"trip_date": None})
    assert resp.status_code == 200
    assert resp.json()["trip_date"] is None


def test_patch_updates_saved_plan_snapshot(client):
    created = _create(client).json()
    new_plan = {"stops": [], "legs": {}}
    resp = client.patch(f"/api/itineraries/{created['id']}", json={"saved_plan": new_plan})
    assert resp.status_code == 200
    assert resp.json()["saved_plan"] == new_plan


# ── Tags ─────────────────────────────────────────────────────────────────────

def test_tags_reused_not_duplicated_within_user(client):
    _create(client, name="Trip 1", tags=["Family"])
    _create(client, name="Trip 2", tags=["Family"])

    # If the tag were duplicated per-itinerary instead of reused, filtering
    # by name would still coincidentally work — the real assertion is the
    # unique constraint on (user_id, name) not raising on the second create.
    resp = client.get("/api/itineraries", params={"tag": "Family"})
    assert resp.json()["total"] == 2


def test_tags_isolated_per_user(client):
    _create(client, name="A's trip", tags=["Family"])
    client.as_user_b()
    _create(client, name="B's trip", tags=["Family"])

    resp = client.get("/api/itineraries", params={"tag": "Family"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "B's trip"


# ── Listing: filtering, sorting, pagination ─────────────────────────────────

def test_upcoming_vs_past_split(client):
    today = dt.date.today()
    past = (today - dt.timedelta(days=10)).isoformat()
    future = (today + dt.timedelta(days=10)).isoformat()
    _create(client, name="Past trip", trip_date=past)
    _create(client, name="Future trip", trip_date=future)
    _create(client, name="Undated trip")

    upcoming = client.get("/api/itineraries", params={"status": "upcoming"}).json()
    assert {i["name"] for i in upcoming["items"]} == {"Future trip", "Undated trip"}

    past_resp = client.get("/api/itineraries", params={"status": "past"}).json()
    assert {i["name"] for i in past_resp["items"]} == {"Past trip"}


def test_pinned_sorts_first_regardless_of_date_sort(client):
    today = dt.date.today()
    _create(client, name="Unpinned soonest", trip_date=today.isoformat())
    _create(
        client,
        name="Pinned later",
        trip_date=(today + dt.timedelta(days=30)).isoformat(),
        is_pinned=True,
    )

    resp = client.get("/api/itineraries", params={"sort": "trip_date", "order": "asc"})
    names = [i["name"] for i in resp.json()["items"]]
    assert names[0] == "Pinned later"


def test_pagination_limit_and_offset(client):
    for i in range(3):
        _create(client, name=f"Trip {i}")

    page1 = client.get("/api/itineraries", params={"limit": 2, "offset": 0}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2

    page2 = client.get("/api/itineraries", params={"limit": 2, "offset": 2}).json()
    assert len(page2["items"]) == 1
