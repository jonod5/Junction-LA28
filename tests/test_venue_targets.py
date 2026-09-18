"""app.services.venue_targets — shared target-row resolution (v1.7 Phase 3)."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base  # noqa: E402
from app.models.venue import CongestionTdm, ParkingOption, TransitAccess, Venue  # noqa: E402
from app.services.venue_targets import find_target_row, get_or_create_target_row  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine, tables=[Venue.__table__, ParkingOption.__table__, CongestionTdm.__table__, TransitAccess.__table__],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    session.add(Venue(id=1, name="Test Arena"))
    session.commit()
    yield session
    session.close()


def test_find_returns_none_when_nothing_exists(db):
    assert find_target_row(db, 1, "parking_option") is None
    assert find_target_row(db, 1, "congestion_tdm") is None


def test_find_ignores_lot_named_rows_for_parking_option(db):
    db.add(ParkingOption(venue_id=1, lot_name="Blue Lot", source="hand-collected"))
    db.commit()
    assert find_target_row(db, 1, "parking_option") is None


def test_find_returns_the_general_parking_row(db):
    general = ParkingOption(venue_id=1, lot_name=None, source="llm_extract:pending")
    db.add(general)
    db.commit()
    found = find_target_row(db, 1, "parking_option")
    assert found.id == general.id


def test_transit_access_requires_entity_id(db):
    stop = TransitAccess(venue_id=1, external_ref="s1", source="gtfs_static")
    db.add(stop)
    db.commit()
    assert find_target_row(db, 1, "transit_access") is None
    assert find_target_row(db, 1, "transit_access", entity_id=stop.id).id == stop.id


def test_get_or_create_creates_lazily_for_parking_option(db):
    assert db.query(ParkingOption).count() == 0
    row = get_or_create_target_row(db, 1, "parking_option")
    assert row.lot_name is None
    assert row.source == "llm_extract:pending"
    assert db.query(ParkingOption).count() == 1


def test_get_or_create_reuses_existing_congestion_row(db):
    existing = CongestionTdm(venue_id=1, arrival_notes="Arrive early.")
    db.add(existing)
    db.commit()
    row = get_or_create_target_row(db, 1, "congestion_tdm")
    assert row.id == existing.id


def test_get_or_create_raises_for_transit_access_without_entity_id(db):
    with pytest.raises(ValueError, match="entity_id"):
        get_or_create_target_row(db, 1, "transit_access")
