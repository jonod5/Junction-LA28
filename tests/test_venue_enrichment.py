"""
Tier-1 automated venue enrichment (v1.7 Phases 1 & 3).

Covers:
  • find_nearest_transit: radius filtering, route lookup, parent-station
    dedup (a platform stop is dropped when its parent station is also in
    range)
  • enrich_venue: writes provenance-tagged TransitAccess rows for brand-new
    stops immediately; a re-run with nothing changed touches nothing; a
    re-run where something changed drafts a pending_change review-queue
    row instead of overwriting the stored value (Phase 3 change detection)
  • hand-collected rows (external_ref=None) are never touched by enrichment
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
from app.models.venue import TransitAccess, Venue, VenueExtraction  # noqa: E402
from app.services.venue_enrichment import enrich_venue, find_nearest_transit  # noqa: E402

# Venue at LA Memorial Coliseum-ish coordinates.
VENUE_LAT, VENUE_LNG = 34.0141, -118.2879
# ~200m away — well within the default 1200m radius.
NEAR_LAT, NEAR_LNG = 34.0159, -118.2879
# ~5km away — well outside it.
FAR_LAT, FAR_LNG = 34.06, -118.2879


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            Venue.__table__, TransitAccess.__table__, VenueExtraction.__table__,
            GtfsStop.__table__, GtfsRoute.__table__, GtfsTrip.__table__, GtfsStopTime.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def _seed_route_at_stop(db, stop_id: str, route_id: str = "40", route_type: int = 3):
    db.add(GtfsRoute(route_id=route_id, route_short_name=route_id, route_long_name="Test Line", route_type=route_type))
    db.add(GtfsTrip(trip_id=f"trip-{stop_id}", route_id=route_id))
    db.add(GtfsStopTime(trip_id=f"trip-{stop_id}", stop_id=stop_id, stop_sequence=1))


class TestFindNearestTransit:
    def test_only_returns_stops_within_radius(self, db):
        db.add(GtfsStop(stop_id="near", stop_name="Near Stop", stop_lat=NEAR_LAT, stop_lon=NEAR_LNG))
        db.add(GtfsStop(stop_id="far", stop_name="Far Stop", stop_lat=FAR_LAT, stop_lon=FAR_LNG))
        _seed_route_at_stop(db, "near")
        db.flush()

        results = find_nearest_transit(db, VENUE_LAT, VENUE_LNG, radius_m=1200)

        assert [r.stop_id for r in results] == ["near"]
        assert results[0].routes[0]["short_name"] == "40"
        assert results[0].routes[0]["mode"] == "bus"

    def test_prefers_parent_station_over_child_platform(self, db):
        db.add(GtfsStop(
            stop_id="parent", stop_name="Union Station", stop_lat=NEAR_LAT, stop_lon=NEAR_LNG, location_type=1,
        ))
        db.add(GtfsStop(
            stop_id="platform-1", stop_name="Union Station Platform 1",
            stop_lat=NEAR_LAT, stop_lon=NEAR_LNG, location_type=0, parent_station="parent",
        ))
        db.flush()

        results = find_nearest_transit(db, VENUE_LAT, VENUE_LNG, radius_m=1200)

        assert [r.stop_id for r in results] == ["parent"]

    def test_respects_limit(self, db):
        for i in range(3):
            db.add(GtfsStop(stop_id=f"s{i}", stop_name=f"Stop {i}", stop_lat=NEAR_LAT, stop_lon=NEAR_LNG))
        db.flush()

        results = find_nearest_transit(db, VENUE_LAT, VENUE_LNG, radius_m=1200, limit=2)

        assert len(results) == 2


class TestEnrichVenue:
    @pytest.fixture(autouse=True)
    def _mock_external_calls(self):
        """Enrichment also calls GBFS/OSM/Directions — mock all three so
        tests never touch the network, and control their output."""
        with (
            patch("app.services.venue_enrichment.gbfs_get_nearby") as gbfs,
            patch("app.services.venue_enrichment.nearby_context") as osm_ctx,
            patch("app.services.venue_enrichment.summarize_context") as osm_summary,
            patch("app.services.venue_enrichment.fetch_directions") as directions,
        ):
            gbfs.return_value = {"items": [], "pricing": {}, "errors": {}}
            osm_ctx.return_value = {"elements": [], "error": None}
            osm_summary.return_value = None
            directions.return_value = {"distance_m": 300, "duration_s": 240, "polyline": "", "steps": []}
            yield {"gbfs": gbfs, "osm_ctx": osm_ctx, "osm_summary": osm_summary, "directions": directions}

    def _seed_venue_and_stop(self, db) -> Venue:
        venue = Venue(name="Test Venue", lat=VENUE_LAT, lng=VENUE_LNG)
        db.add(venue)
        db.flush()
        db.add(GtfsStop(stop_id="near", stop_name="Near Stop", stop_lat=NEAR_LAT, stop_lon=NEAR_LNG))
        _seed_route_at_stop(db, "near")
        db.flush()
        return venue

    def test_creates_reviewed_row_with_provenance(self, db):
        venue = self._seed_venue_and_stop(db)

        result = enrich_venue(db, venue)
        db.commit()

        assert result.rows_created == 1
        assert result.rows_unchanged == 0
        assert result.changes_flagged == 0
        rows = db.query(TransitAccess).filter(TransitAccess.venue_id == venue.id).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.external_ref == "near"
        assert row.reviewed is True
        assert row.confidence == "high"
        assert row.source.startswith("gtfs_static")
        assert row.retrieved_at is not None
        assert row.rideshare_estimate_usd is not None
        assert venue.reviewed is True

    def test_rerun_with_nothing_changed_touches_nothing(self, db):
        venue = self._seed_venue_and_stop(db)
        enrich_venue(db, venue)
        db.commit()

        result = enrich_venue(db, venue)
        db.commit()

        assert result.rows_created == 0
        assert result.rows_unchanged == 1
        assert result.changes_flagged == 0
        rows = db.query(TransitAccess).filter(TransitAccess.venue_id == venue.id).all()
        assert len(rows) == 1
        assert db.query(VenueExtraction).count() == 0

    def test_rerun_with_changed_field_drafts_pending_change_not_overwrite(self, db, _mock_external_calls):
        venue = self._seed_venue_and_stop(db)
        enrich_venue(db, venue)
        db.commit()
        original_row = db.query(TransitAccess).filter(TransitAccess.venue_id == venue.id).first()
        original_line = original_row.line

        # A route renumbering: the stop is now served by a different line.
        db.add(GtfsRoute(route_id="204", route_short_name="204", route_long_name="Renumbered", route_type=3))
        db.add(GtfsTrip(trip_id="trip-near-204", route_id="204"))
        db.add(GtfsStopTime(trip_id="trip-near-204", stop_id="near", stop_sequence=1))
        db.flush()

        result = enrich_venue(db, venue)
        db.commit()

        assert result.rows_created == 0
        assert result.changes_flagged == 1
        db.refresh(original_row)
        # The stored row is untouched — the change was drafted, not applied.
        assert original_row.line == original_line

        draft = db.query(VenueExtraction).filter(
            VenueExtraction.entity_type == "transit_access", VenueExtraction.field_name == "line",
        ).first()
        assert draft is not None
        assert draft.status == "pending_change"
        assert draft.entity_id == original_row.id
        assert draft.previous_value == original_line
        assert "204" in draft.extracted_value

    def test_rerun_replaces_stale_pending_change_draft(self, db, _mock_external_calls):
        venue = self._seed_venue_and_stop(db)
        enrich_venue(db, venue)
        db.commit()
        row = db.query(TransitAccess).filter(TransitAccess.venue_id == venue.id).first()

        db.add(GtfsRoute(route_id="204", route_short_name="204", route_long_name="First change", route_type=3))
        db.add(GtfsTrip(trip_id="trip-near-204", route_id="204"))
        db.add(GtfsStopTime(trip_id="trip-near-204", stop_id="near", stop_sequence=1))
        db.flush()
        enrich_venue(db, venue)
        db.commit()
        assert db.query(VenueExtraction).filter(VenueExtraction.field_name == "line").count() == 1

        db.add(GtfsRoute(route_id="999", route_short_name="999", route_long_name="Second change", route_type=3))
        db.add(GtfsTrip(trip_id="trip-near-999", route_id="999"))
        db.add(GtfsStopTime(trip_id="trip-near-999", stop_id="near", stop_sequence=1))
        db.flush()
        enrich_venue(db, venue)
        db.commit()

        line_drafts = db.query(VenueExtraction).filter(VenueExtraction.field_name == "line").all()
        assert len(line_drafts) == 1
        assert "999" in line_drafts[0].extracted_value
        assert line_drafts[0].previous_value == row.line  # still diffed against the original stored value

    def test_never_touches_hand_collected_rows(self, db):
        venue = self._seed_venue_and_stop(db)
        hand_collected = TransitAccess(
            venue_id=venue.id, line="Hand-entered Line", source="https://example.com", reviewed=True,
        )
        db.add(hand_collected)
        db.flush()

        enrich_venue(db, venue)
        db.commit()

        db.refresh(hand_collected)
        assert hand_collected.line == "Hand-entered Line"
        assert hand_collected.external_ref is None
        # Enrichment added its own row alongside, didn't touch or replace this one.
        rows = db.query(TransitAccess).filter(TransitAccess.venue_id == venue.id).all()
        assert len(rows) == 2

    def test_raises_for_venue_without_coordinates(self, db):
        venue = Venue(name="No Coords Venue")
        db.add(venue)
        db.flush()

        with pytest.raises(ValueError, match="no coordinates"):
            enrich_venue(db, venue)

    def test_falls_back_to_haversine_when_directions_unavailable(self, db, _mock_external_calls):
        from app.routers.directions import DirectionsError

        _mock_external_calls["directions"].side_effect = DirectionsError("no key configured", status_code=500)
        venue = self._seed_venue_and_stop(db)

        enrich_venue(db, venue)
        db.commit()

        row = db.query(TransitAccess).filter(TransitAccess.venue_id == venue.id).first()
        assert row.confidence == "estimated"
        assert "haversine_estimate" in row.source
        assert row.rideshare_estimate_usd is not None
