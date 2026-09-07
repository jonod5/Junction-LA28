"""
GET /api/venues/{id} never presents an unreviewed TransitAccess row as fact
(v1.7 Phase 1) — a reviewed=False row (as Tier-2 extraction will produce
starting Phase 2) is excluded from the response entirely, while reviewed=True
rows — hand-collected or Tier-1 pipeline-written — still show normally.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.models.venue import (  # noqa: E402
    CongestionTdm,
    CurbDropoff,
    ParkingOption,
    TransitAccess,
    Venue,
)


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Venue.__table__, ParkingOption.__table__, CongestionTdm.__table__,
            TransitAccess.__table__, CurbDropoff.__table__,
        ],
    )
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    seed = TestSessionLocal()
    venue = Venue(id=1, name="Test Arena")
    seed.add(venue)
    seed.flush()
    seed.add(TransitAccess(
        venue_id=1, line="Reviewed Line", stop_name="Reviewed Stop", source="gtfs_static", reviewed=True,
    ))
    seed.add(TransitAccess(
        venue_id=1, line="Unreviewed Line", stop_name="Draft Stop", source="llm_extract", reviewed=False,
    ))
    seed.commit()
    seed.close()

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_unreviewed_transit_row_excluded_from_response(client):
    resp = client.get("/api/venues/1")
    assert resp.status_code == 200
    lines = [t["line"] for t in resp.json()["transit_accesses"]]
    assert "Reviewed Line" in lines
    assert "Unreviewed Line" not in lines


def test_reviewed_row_still_includes_new_rideshare_field(client):
    resp = client.get("/api/venues/1")
    reviewed = next(t for t in resp.json()["transit_accesses"] if t["line"] == "Reviewed Line")
    assert "rideshare_estimate_usd" in reviewed
