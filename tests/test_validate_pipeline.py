"""
app.validate_pipeline — the gold-standard validation harness (v1.7 Phase 3).

Only the pure/read-only helper functions are covered here (mocking the
underlying feed/LLM calls); the CLI's argparse plumbing and print
formatting are exercised live in the build-log smoke test instead, same
precedent as the enrich/extract CLIs.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base  # noqa: E402
from app.models.gtfs import GtfsRoute, GtfsStop, GtfsStopTime, GtfsTrip  # noqa: E402
from app.models.venue import Venue, VenueSource  # noqa: E402
from app.validate_pipeline import _print_summary, _validate_tier1, _validate_tier2  # noqa: E402


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Venue.__table__, VenueSource.__table__,
            GtfsStop.__table__, GtfsRoute.__table__, GtfsTrip.__table__, GtfsStopTime.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestValidateTier1:
    def test_reports_no_coordinates(self, db):
        venue = Venue(name="No Coords", is_gold_standard=True)
        db.add(venue)
        db.flush()
        result = _validate_tier1(db, venue)
        assert result == {"ok": False, "reason": "no coordinates"}

    def test_counts_stops_micromobility_and_osm(self, db):
        venue = Venue(name="Gold Venue", lat=34.0141, lng=-118.2879, is_gold_standard=True)
        db.add(venue)
        db.add(GtfsStop(stop_id="s1", stop_name="Near Stop", stop_lat=34.0142, stop_lon=-118.2879))
        db.flush()

        with (
            patch("app.validate_pipeline.gbfs_get_nearby") as gbfs,
            patch("app.validate_pipeline.nearby_context") as osm,
        ):
            gbfs.return_value = {"items": [{"id": "bike-1"}], "pricing": {}, "errors": {}}
            osm.return_value = {"elements": [{"id": 1}, {"id": 2}], "error": None}
            result = _validate_tier1(db, venue)

        assert result["ok"] is True
        assert result["stops_found"] == 1
        assert result["micromobility_found"] == 1
        assert result["osm_elements_found"] == 2


class TestValidateTier2:
    def test_reports_no_source_urls(self, db):
        venue = Venue(name="No Sources", is_gold_standard=True)
        db.add(venue)
        db.flush()
        result = _validate_tier2(venue)
        assert result == {"ok": False, "reason": "no source URLs"}


class TestPrintSummary:
    def test_computes_percentage_of_venues_with_a_result(self, capsys):
        results = [
            (object(), {"ok": True, "stops_found": 2}),
            (object(), {"ok": True, "stops_found": 0}),
            (object(), {"ok": False, "reason": "no coordinates"}),
        ]
        _print_summary("Tier 1", results, key="stops_found")
        out = capsys.readouterr().out
        assert "1/2" in out
        assert "50%" in out

    def test_no_checkable_venues(self, capsys):
        _print_summary("Tier 1", [(object(), {"ok": False, "reason": "x"})], key="stops_found")
        out = capsys.readouterr().out
        assert "no venues could be checked" in out
