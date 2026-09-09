"""
Admin review-queue API — /api/venues/review-queue/* (v1.7 Phase 2).

Covers:
  • admin guard (missing/wrong X-Admin-Key)
  • approve copies the extracted value into a real row with provenance, and
    marks the draft approved
  • approve refuses to overwrite a field that already has a value — the
    safety net that keeps hand-collected/gold-standard data untouched
  • edit applies the corrected value instead of the extracted one
  • reject never touches ParkingOption/CurbDropoff/CongestionTdm
  • a decision on an already-reviewed draft 409s
  • approving one draft supersedes any other still-pending draft for the
    exact same venue/entity_type/field_name
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from datetime import datetime, timezone  # noqa: E402

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
    VenueExtraction,
)


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Venue.__table__, ParkingOption.__table__, CurbDropoff.__table__,
            CongestionTdm.__table__, TransitAccess.__table__, VenueExtraction.__table__,
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
    seed.commit()
    seed.close()

    monkeypatch.setenv("VENUE_ADMIN_KEY", "test-admin-key")

    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    c.session_local = TestSessionLocal
    yield c
    app.dependency_overrides.clear()


def _seed_draft(client, **overrides) -> int:
    db = client.session_local()
    defaults = dict(
        venue_id=1, entity_type="parking_option", field_name="price_notes",
        extracted_value="$20 flat rate", source_url="https://example.com/parking",
        source_quote="Parking is a flat $20.", confidence=0.9, status="pending",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    draft = VenueExtraction(**defaults)
    db.add(draft)
    db.commit()
    draft_id = draft.id
    db.close()
    return draft_id


ADMIN_HEADERS = {"X-Admin-Key": "test-admin-key"}


def test_list_requires_admin_key(client):
    resp = client.get("/api/venues/review-queue")
    assert resp.status_code == 401


def test_list_rejects_wrong_admin_key(client):
    resp = client.get("/api/venues/review-queue", headers={"X-Admin-Key": "wrong"})
    assert resp.status_code == 401


def test_list_returns_pending_drafts_by_default(client):
    _seed_draft(client)
    resp = client.get("/api/venues/review-queue", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "pending"
    assert body[0]["source_quote"] == "Parking is a flat $20."


def test_approve_writes_value_with_provenance_and_marks_draft_approved(client):
    draft_id = _seed_draft(client)
    resp = client.post(
        f"/api/venues/review-queue/{draft_id}/decision",
        json={"decision": "approve", "reviewed_by": "JD"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    db = client.session_local()
    row = db.query(ParkingOption).filter(ParkingOption.venue_id == 1).first()
    assert row is not None
    assert row.price_notes == "$20 flat rate"
    assert row.reviewed is True
    assert row.confidence == "high"
    assert row.source == "llm_extract:https://example.com/parking"
    assert row.lot_name is None


def test_approve_refuses_to_overwrite_existing_value(client):
    db = client.session_local()
    db.add(ParkingOption(
        venue_id=1, lot_name=None, price_notes="Hand-collected: $15",
        source="https://example.com/hand-collected", reviewed=True,
    ))
    db.commit()
    db.close()

    draft_id = _seed_draft(client)
    resp = client.post(
        f"/api/venues/review-queue/{draft_id}/decision",
        json={"decision": "approve"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 409

    db = client.session_local()
    row = db.query(ParkingOption).filter(ParkingOption.venue_id == 1).first()
    assert row.price_notes == "Hand-collected: $15"
    db.close()


def test_edit_applies_corrected_value(client):
    draft_id = _seed_draft(client)
    resp = client.post(
        f"/api/venues/review-queue/{draft_id}/decision",
        json={"decision": "edit", "corrected_value": "$22, cash only"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "edited"

    db = client.session_local()
    row = db.query(ParkingOption).filter(ParkingOption.venue_id == 1).first()
    assert row.price_notes == "$22, cash only"


def test_reject_never_touches_real_tables(client):
    draft_id = _seed_draft(client)
    resp = client.post(
        f"/api/venues/review-queue/{draft_id}/decision",
        json={"decision": "reject"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    db = client.session_local()
    assert db.query(ParkingOption).count() == 0


def test_decision_on_already_reviewed_draft_conflicts(client):
    draft_id = _seed_draft(client, status="approved")
    resp = client.post(
        f"/api/venues/review-queue/{draft_id}/decision",
        json={"decision": "reject"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 409


def test_approving_one_draft_supersedes_conflicting_pending_draft(client):
    first_id = _seed_draft(client, extracted_value="$20", source_url="https://a.example.com")
    second_id = _seed_draft(client, extracted_value="$25", source_url="https://b.example.com")

    resp = client.post(
        f"/api/venues/review-queue/{first_id}/decision",
        json={"decision": "approve"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200

    db = client.session_local()
    second = db.get(VenueExtraction, second_id)
    assert second.status == "superseded"
