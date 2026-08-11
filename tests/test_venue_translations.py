"""
Venue detail translation (v1.5 Phase 3) — /api/venues/{id}?language=.

Covers:
  • translated value returned when a language + translation row exist
  • falls back to English when the language is unsupported, omitted, or a
    specific field just has no translation row
  • identifiers (lot_name) are never translated, even if a row existed for
    them — the router only ever looks up the prose fields
  • a translation for one venue never leaks onto another venue's row with
    the same field name (translations are looked up by entity_id, not just
    field name)
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from unittest.mock import patch  # noqa: E402

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
    VenueTranslation,
)
from app.routers.venues import _normalize_language  # noqa: E402


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Venue.__table__, ParkingOption.__table__, CongestionTdm.__table__,
            TransitAccess.__table__, CurbDropoff.__table__, VenueTranslation.__table__,
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
    v1 = Venue(id=1, name="Test Arena", capacity_text="100 spaces available")
    v2 = Venue(id=2, name="Other Arena", capacity_text="100 spaces available")
    seed.add_all([v1, v2])
    seed.flush()
    seed.add(ParkingOption(id=1, venue_id=1, lot_name="Blue Lot", notes="Closest to the main gate.", source="test"))
    seed.add(CongestionTdm(id=1, venue_id=1, arrival_notes="Arrive 2 hours early."))
    seed.add(VenueTranslation(
        venue_id=1, entity_type="venue", entity_id=1, field="capacity_text",
        language="es", value="100 espacios disponibles",
    ))
    seed.add(VenueTranslation(
        venue_id=1, entity_type="parking_option", entity_id=1, field="notes",
        language="es", value="Lo más cercano a la puerta principal.",
    ))
    seed.add(VenueTranslation(
        venue_id=1, entity_type="congestion_tdm", entity_id=1, field="arrival_notes",
        language="fr", value="Arrivez 2 heures à l'avance.",
    ))
    seed.commit()
    seed.close()

    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}), patch("app.main._wait_for_db", return_value=None):
        from app.main import app

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


def test_no_language_param_returns_english(client):
    resp = client.get("/api/venues/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["capacity_text"] == "100 spaces available"
    assert body["parking_options"][0]["notes"] == "Closest to the main gate."


def test_translated_language_returns_translation(client):
    resp = client.get("/api/venues/1?language=es")
    body = resp.json()
    assert body["capacity_text"] == "100 espacios disponibles"
    assert body["parking_options"][0]["notes"] == "Lo más cercano a la puerta principal."


def test_falls_back_to_english_when_field_has_no_translation_row(client):
    # congestion_tdm.arrival_notes only has an "fr" row, not "es" — a
    # signed-out-into-Spanish user must still see the English text, not a
    # blank field.
    resp = client.get("/api/venues/1?language=es")
    body = resp.json()
    assert body["congestion_tdm"]["arrival_notes"] == "Arrive 2 hours early."

    resp_fr = client.get("/api/venues/1?language=fr")
    assert resp_fr.json()["congestion_tdm"]["arrival_notes"] == "Arrivez 2 heures à l'avance."


def test_unsupported_language_code_falls_back_to_english(client):
    resp = client.get("/api/venues/1?language=de")
    assert resp.json()["capacity_text"] == "100 spaces available"


def test_missing_language_param_and_language_en_both_return_english(client):
    assert client.get("/api/venues/1").json()["capacity_text"] == "100 spaces available"
    assert client.get("/api/venues/1?language=en").json()["capacity_text"] == "100 spaces available"


def test_identifier_fields_never_translated(client):
    # lot_name is an identifier — even though a translation exists for this
    # same parking_option row's "notes" field, lot_name must render in its
    # original form regardless of language.
    resp = client.get("/api/venues/1?language=es")
    assert resp.json()["parking_options"][0]["lot_name"] == "Blue Lot"


def test_translation_scoped_to_its_own_venue(client):
    # Venue 2 has the identical English capacity_text as venue 1 but no
    # translation row of its own — it must not pick up venue 1's Spanish
    # translation just because the field name and English text match.
    resp = client.get("/api/venues/2?language=es")
    assert resp.json()["capacity_text"] == "100 spaces available"


def test_normalize_language_helper():
    assert _normalize_language("es") == "es"
    assert _normalize_language("fr") == "fr"
    assert _normalize_language("zh-Hans") == "zh-Hans"
    assert _normalize_language("en") is None
    assert _normalize_language(None) is None
    assert _normalize_language("klingon") is None
