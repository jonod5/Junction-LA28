"""
Tier-2 LLM-assisted extraction (v1.7 Phases 2 & 3).

Covers:
  • only fields with both a value and a quote are drafted — the model
    declining to extract (omitting a field) is exactly what should happen,
    not an error
  • fields outside FIELD_SPEC are dropped, not silently written
  • a re-run replaces outstanding drafts rather than duplicating them
  • already-reviewed rows are never touched by a re-run
  • no source URLs (no VenueSource rows, no override) raises ValueError
  • change detection (Phase 3): an extracted value that matches what's
    already stored drafts nothing; one that differs drafts a
    "pending_change" with previous_value set, not a plain "pending"
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from datetime import datetime, timezone  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base  # noqa: E402
from app.models.venue import ParkingOption, Venue, VenueExtraction, VenueSource  # noqa: E402
from app.services.venue_extract import extract_venue  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[Venue.__table__, VenueSource.__table__, VenueExtraction.__table__, ParkingOption.__table__],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _mock_fetch():
    with patch("app.services.venue_extract._fetch_page") as fetch:
        fetch.return_value = "Parking costs $20. Rideshare pickup is at the north gate."
        yield fetch


def _seed_venue_with_source(db, url="https://example.com/parking") -> Venue:
    venue = Venue(name="Test Venue")
    db.add(venue)
    db.flush()
    db.add(VenueSource(venue_id=venue.id, primary_url=url))
    db.flush()
    return venue


class TestExtractVenue:
    def test_drafts_only_fields_with_value_and_quote(self, db):
        venue = _seed_venue_with_source(db)
        with patch("app.services.venue_extract._extract_fields_from_page") as extract:
            extract.return_value = [
                {
                    "entity_type": "parking_option", "field_name": "price_notes",
                    "value": "$20", "quote": "Parking costs $20.", "confidence": 0.9,
                },
                {
                    # Model declined — no value/quote. Must be dropped, not written as null.
                    "entity_type": "parking_option", "field_name": "surge_notes",
                    "value": None, "quote": None, "confidence": None,
                },
            ]
            result = extract_venue(db, venue)
        db.commit()

        assert result.fields_drafted == 1
        rows = db.query(VenueExtraction).filter(VenueExtraction.venue_id == venue.id).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.field_name == "price_notes"
        assert row.extracted_value == "$20"
        assert row.source_quote == "Parking costs $20."
        assert row.status == "pending"

    def test_drops_fields_outside_field_spec(self, db):
        venue = _seed_venue_with_source(db)
        with patch("app.services.venue_extract._extract_fields_from_page") as extract:
            extract.return_value = [
                {"entity_type": "venue", "field_name": "name", "value": "x", "quote": "x", "confidence": 0.9},
            ]
            result = extract_venue(db, venue)
        db.commit()

        assert result.fields_drafted == 0
        assert db.query(VenueExtraction).count() == 0

    def test_rerun_replaces_pending_drafts(self, db):
        venue = _seed_venue_with_source(db)
        with patch("app.services.venue_extract._extract_fields_from_page") as extract:
            extract.return_value = [
                {"entity_type": "parking_option", "field_name": "price_notes",
                 "value": "$20", "quote": "Parking costs $20.", "confidence": 0.9},
            ]
            extract_venue(db, venue)
            db.commit()

            extract.return_value = [
                {"entity_type": "parking_option", "field_name": "price_notes",
                 "value": "$25", "quote": "Parking costs $25 now.", "confidence": 0.9},
            ]
            extract_venue(db, venue)
            db.commit()

        rows = db.query(VenueExtraction).filter(VenueExtraction.venue_id == venue.id).all()
        assert len(rows) == 1
        assert rows[0].extracted_value == "$25"

    def test_never_touches_reviewed_rows(self, db):
        venue = _seed_venue_with_source(db)
        approved = VenueExtraction(
            venue_id=venue.id, entity_type="parking_option", field_name="notes",
            extracted_value="approved value", source_url="https://example.com/parking",
            source_quote="quote", confidence=0.9, status="approved",
            created_at=datetime.now(timezone.utc),
        )
        db.add(approved)
        db.flush()

        with patch("app.services.venue_extract._extract_fields_from_page") as extract:
            extract.return_value = []
            extract_venue(db, venue)
        db.commit()

        db.refresh(approved)
        assert approved.status == "approved"
        assert approved.extracted_value == "approved value"

    def test_raises_without_source_urls(self, db):
        venue = Venue(name="No Sources Venue")
        db.add(venue)
        db.flush()

        with pytest.raises(ValueError, match="no source URLs"):
            extract_venue(db, venue)

    def test_matching_extracted_value_drafts_nothing(self, db):
        venue = _seed_venue_with_source(db)
        db.add(ParkingOption(venue_id=venue.id, lot_name=None, price_notes="$20", source="hand-collected"))
        db.flush()

        with patch("app.services.venue_extract._extract_fields_from_page") as extract:
            extract.return_value = [
                {"entity_type": "parking_option", "field_name": "price_notes",
                 "value": "$20", "quote": "Parking costs $20.", "confidence": 0.9},
            ]
            result = extract_venue(db, venue)
        db.commit()

        assert result.fields_drafted == 0
        assert result.changes_flagged == 0
        assert db.query(VenueExtraction).count() == 0

    def test_differing_extracted_value_drafts_pending_change(self, db):
        venue = _seed_venue_with_source(db)
        existing = ParkingOption(venue_id=venue.id, lot_name=None, price_notes="$15", source="hand-collected")
        db.add(existing)
        db.flush()

        with patch("app.services.venue_extract._extract_fields_from_page") as extract:
            extract.return_value = [
                {"entity_type": "parking_option", "field_name": "price_notes",
                 "value": "$20", "quote": "Parking costs $20.", "confidence": 0.9},
            ]
            result = extract_venue(db, venue)
        db.commit()

        assert result.fields_drafted == 0
        assert result.changes_flagged == 1
        draft = db.query(VenueExtraction).filter(VenueExtraction.venue_id == venue.id).first()
        assert draft.status == "pending_change"
        assert draft.previous_value == "$15"
        assert draft.extracted_value == "$20"
        assert draft.entity_id == existing.id
        # The hand-collected row itself is untouched.
        db.refresh(existing)
        assert existing.price_notes == "$15"
