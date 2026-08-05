"""Account management — /api/account.

Same TestClient + dependency-override pattern as test_itineraries.py.
Supabase's Admin API is mocked (a fake httpx.Client) — these tests never hit
a real Supabase project.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from unittest.mock import patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import Depends, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth import get_current_user  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.models.itinerary import Itinerary, ItineraryTag, itinerary_tag_link  # noqa: E402
from app.models.user import User  # noqa: E402

USER_ID = "a0000000-0000-0000-0000-000000000001"


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _FakeHttpxClient:
    """Stand-in for httpx.Client — records the delete() call and returns a
    configurable status code, so tests never hit a real Supabase project."""

    last_call: dict | None = None
    next_status = 200

    def __init__(self, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def delete(self, url, headers=None):
        _FakeHttpxClient.last_call = {"url": url, "headers": headers}
        return _FakeResponse(_FakeHttpxClient.next_status)


class _RaisingHttpxClient(_FakeHttpxClient):
    def delete(self, url, headers=None):
        raise httpx.ConnectError("connection refused")


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # SQLite doesn't enforce foreign keys (including ON DELETE CASCADE) by
    # default, unlike Postgres — without this, the cascade test would pass
    # or fail based on nothing but the test DB's default, not real behavior.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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

    def db_lookup(db: Session = Depends(get_db)) -> User:
        # Depends on get_db (not a standalone session) so this shares the
        # same request-scoped session as the route's own `db` parameter —
        # FastAPI caches Depends(get_db) per request, exactly like the real
        # get_current_user does. Without that, db.refresh(user) in
        # update_account fails because `user` would belong to a different,
        # already-closed session.
        user = db.get(User, USER_ID)
        if user is None:
            raise HTTPException(status_code=401, detail="No such user")
        return user

    seed = TestSessionLocal()
    seed.add(User(id=USER_ID, email="rider@example.com", display_name="Rider One"))
    seed.commit()
    seed.close()

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role-key")
    _FakeHttpxClient.last_call = None
    _FakeHttpxClient.next_status = 200

    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}), patch(
        "app.main._wait_for_db", return_value=None
    ):
        from app.main import app

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = db_lookup

        with TestClient(app) as c:
            c.app = app
            c.session_local = TestSessionLocal
            yield c

        app.dependency_overrides.clear()


def test_get_account_returns_profile(client):
    resp = client.get("/api/account")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == USER_ID
    assert body["email"] == "rider@example.com"
    assert body["display_name"] == "Rider One"
    assert body["preferences"] == {}


def test_patch_updates_display_name_only(client):
    resp = client.patch("/api/account", json={"display_name": "New Name"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "New Name"
    assert body["preferences"] == {}


def test_patch_updates_default_modes_without_touching_display_name(client):
    resp = client.patch("/api/account", json={"default_modes": ["walk", "transit"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Rider One"
    assert body["preferences"] == {"default_modes": ["walk", "transit"]}


def test_patch_default_modes_round_trips_and_overwrites_cleanly(client):
    client.patch("/api/account", json={"default_modes": ["walk"]})
    assert client.get("/api/account").json()["preferences"] == {"default_modes": ["walk"]}
    resp = client.patch("/api/account", json={"default_modes": ["bike", "scooter"]})
    assert resp.json()["preferences"] == {"default_modes": ["bike", "scooter"]}


@patch("app.routers.account.httpx.Client", _FakeHttpxClient)
def test_delete_account_calls_supabase_admin_api_then_deletes_locally(client):
    resp = client.delete("/api/account")
    assert resp.status_code == 204
    assert _FakeHttpxClient.last_call["url"] == f"https://project.supabase.co/auth/v1/admin/users/{USER_ID}"
    assert _FakeHttpxClient.last_call["headers"]["apikey"] == "service-role-key"
    # get_current_user's own 401 semantics kick back in once the row is gone.
    assert client.get("/api/account").status_code == 401


@patch("app.routers.account.httpx.Client", _FakeHttpxClient)
def test_delete_account_cascades_itineraries(client):
    created = client.post("/api/itineraries", json={"name": "Trip", "saved_plan": {}})
    assert created.status_code == 201
    itinerary_id = created.json()["id"]

    resp = client.delete("/api/account")
    assert resp.status_code == 204

    # user row is gone so the authenticated endpoint 401s now — verify the
    # cascade landed by querying the DB directly instead.
    db = client.session_local()
    assert db.get(Itinerary, itinerary_id) is None
    db.close()


@patch("app.routers.account.httpx.Client", _FakeHttpxClient)
def test_delete_account_treats_404_as_success(client):
    _FakeHttpxClient.next_status = 404
    resp = client.delete("/api/account")
    assert resp.status_code == 204


@patch("app.routers.account.httpx.Client", _FakeHttpxClient)
def test_delete_account_502_on_supabase_error_leaves_local_row_intact(client):
    _FakeHttpxClient.next_status = 500
    resp = client.delete("/api/account")
    assert resp.status_code == 502
    # Local row must survive so the delete can be safely retried.
    assert client.get("/api/account").status_code == 200


@patch("app.routers.account.httpx.Client", _RaisingHttpxClient)
def test_delete_account_502_on_network_error(client):
    resp = client.delete("/api/account")
    assert resp.status_code == 502
    assert client.get("/api/account").status_code == 200


def test_delete_account_skips_supabase_call_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    resp = client.delete("/api/account")
    assert resp.status_code == 204


def test_missing_auth_is_401(client):
    del client.app.dependency_overrides[get_current_user]
    resp = client.get("/api/account")
    assert resp.status_code == 401
