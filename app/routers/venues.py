"""
GET /api/venues/{id} — full venue detail for the info panel.

Design choices:
- Returns the full venue detail in a single call so the info panel can render
  without a waterfall of follow-up requests.
- GAMES_TIME_PARKING_POLICY is injected at serialisation time (it's a Python
  constant, not a DB column) so the client always gets the current value
  without a separate /config call.
- Parking options, transit accesses, curb dropoffs, and congestion are all
  loaded via SQLAlchemy relationship (eager via joined load would also work;
  the default lazy load is fine for a single-venue endpoint).
- Float conversion on lat/lng/price_min/price_max: SQLAlchemy returns Decimal
  for Numeric columns; Pydantic coerces them to float automatically when
  from_attributes=True, but we convert explicitly here to be safe with any
  future serialisation path.
- 404 uses the same pattern as the trips router for consistency.
- Provenance stripping: the venue-collection notes were hand-written with
  inline citation asides — "(own research)", "(per the 11/8/2025 UCLA game
  page)", "(not verified officially)" — mixed directly into the prose. Those
  are exactly right for the research record but wrong for a consumer screen,
  so _strip_provenance() removes them from every free-text field in THIS
  API's output only.  The underlying rows (and each row's separate `source` /
  `verified_at` columns) are untouched — provenance stays queryable in the
  data layer, it just never renders.
- Translation (v1.5 Phase 3): an optional `language` query param selects a
  translated value for each *prose* field from venue_translation, falling
  back to the stripped English value whenever a translation is missing
  (untranslated language, or that specific field never got one). Identifiers
  — venue name, zone, address, lot names, transit line/stop/station names,
  bus_lines_serving — are deliberately NEVER looked up in the translation
  table; they render in their original form in every language (see
  frontend/locales/README.md's "don't translate identifiers" rule, applied
  here to dynamic DB content instead of static UI strings). Translations are
  keyed on the *stripped* English text's meaning, not the raw DB value —
  they were written against what _strip_provenance() actually outputs.
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.venue import (
    GAMES_TIME_PARKING_POLICY,
    Venue,
    VenueTranslation,
)
from app.schemas import (
    CongestionOut,
    CurbOut,
    ParkingOut,
    TransitOut,
    VenueDetailOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/venues", tags=["venues"])

# Keep in sync with frontend/lib/i18n.ts's SUPPORTED_LANGUAGES. "en" is
# deliberately excluded — English never has (or needs) a translation row.
_TRANSLATABLE_LANGUAGES = frozenset({"es", "fr", "zh-Hans"})


def _normalize_language(language: str | None) -> str | None:
    """None means "render English" — the caller skips translation lookup entirely."""
    return language if language in _TRANSLATABLE_LANGUAGES else None


class _Translator:
    """Looks up a translated value for one venue's fields, falling back to
    the (already provenance-stripped) English value when none exists."""

    def __init__(self, db: Session, venue_id: int, language: str | None):
        self._by_key: dict[tuple[str, int, str], str] = {}
        if language:
            rows = (
                db.query(VenueTranslation)
                .filter(VenueTranslation.venue_id == venue_id, VenueTranslation.language == language)
                .all()
            )
            self._by_key = {(r.entity_type, r.entity_id, r.field): r.value for r in rows}

    def __call__(self, entity_type: str, entity_id: int, field: str, english: str | None) -> str | None:
        if english is None:
            return None
        return self._by_key.get((entity_type, entity_id, field), english)


def _float(val) -> float | None:
    """Convert Decimal or None to float for JSON serialisation."""
    return float(val) if val is not None else None


# Parenthetical asides that cite a source or flag verification status, e.g.
# "(own research)", "(per Metro's own blog)", "(lacoliseum.com, 2023 PDF, lot
# names)", "(not verified officially)".  Matched case-insensitively; only a
# parenthetical CONTAINING one of these markers is removed, so parentheticals
# that are actual data (e.g. "(6 mins)") are left alone.
_PROVENANCE_RE = re.compile(
    r"\([^()]*\b(?:own research|per\b|pdf|unverified|not verified|verified)\b[^()]*\)",
    re.IGNORECASE,
)

# Some fields lead with a bare "Own research:" label instead of tucking the
# citation into parens, e.g. gbfs_dock_description="Own research: No
# scooter/dock zones nearby". Strip the label, keep the data after it.
_LEADING_LABEL_RE = re.compile(r"^\s*own research\s*:\s*", re.IGNORECASE)

# A citation aside can also span a whole sentence rather than staying
# parenthetical, e.g. "A Reddit mention (not verified officially) cited $33
# lot pricing for a 2025 concert — flagging as unverified rather than
# treating as fact." Naming a source like this is unambiguously a citation,
# never consumer-facing content, so the entire sentence goes.
_CITATION_SENTENCE_RE = re.compile(
    r"(?:^|(?<=[.!?]\s))[^.!?]*\breddit\b[^.!?]*[.!?]",
    re.IGNORECASE,
)

# Some fields hold a whole-value research placeholder instead of an inline
# aside — e.g. arrival_notes="not stated in source" — meaning "we found no
# value for this," not an actual note. Those are just as much an internal
# collection artifact as the parenthetical citations above, so treat an
# entire cleaned field matching one of these (case-insensitive, punctuation
# aside) as absent rather than displaying it as content.
_NO_DATA_PLACEHOLDERS = {"not stated", "not stated in source", "no data", "n/a", "unknown", "tbd"}


def _strip_provenance(text: str | None) -> str | None:
    """Remove inline citation/provenance asides from a free-text field."""
    if not text:
        return None
    cleaned = _LEADING_LABEL_RE.sub("", text)
    cleaned = _PROVENANCE_RE.sub("", cleaned)
    cleaned = _CITATION_SENTENCE_RE.sub("", cleaned)
    # Collapse double spaces and stray space-before-punctuation left by the
    # removal, then trim.
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = cleaned.strip()
    if cleaned.lower().rstrip(".") in _NO_DATA_PLACEHOLDERS:
        return None
    return cleaned or None


@router.get("/{venue_id}", response_model=VenueDetailOut)
def get_venue(
    venue_id: int,
    language: str | None = Query(None, description="App locale code (es/fr/zh-Hans); omit or 'en' for English"),
    db: Session = Depends(get_db),
):
    """
    Return full venue detail: identity, parking, transit, curb, congestion,
    games_time_access_notes, and the program-level parking policy constant.
    """
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail=f"Venue {venue_id} not found")

    tr = _Translator(db, venue_id, _normalize_language(language))

    # Build nested schemas from the ORM relationships.  Every free-text field
    # goes through _strip_provenance() — see module docstring. Prose fields
    # additionally go through tr() for a translated value; identifiers (lot
    # names, line/stop/station names, bus_lines_serving) never do.
    parking = [
        ParkingOut(
            id=p.id,
            lot_name=_strip_provenance(p.lot_name),
            is_official=p.is_official,
            price_min=_float(p.price_min),
            price_max=_float(p.price_max),
            price_notes=tr("parking_option", p.id, "price_notes", _strip_provenance(p.price_notes)),
            pricing_basis=tr("parking_option", p.id, "pricing_basis", _strip_provenance(p.pricing_basis)),
            has_surge_pricing=p.has_surge_pricing,
            surge_notes=tr("parking_option", p.id, "surge_notes", _strip_provenance(p.surge_notes)),
            is_closest_to_entrance=p.is_closest_to_entrance,
            notes=tr("parking_option", p.id, "notes", _strip_provenance(p.notes)),
        )
        for p in venue.parking_options
    ]

    transit = [
        TransitOut(
            id=t.id,
            line=_strip_provenance(t.line),
            mode=t.mode,
            stop_name=_strip_provenance(t.stop_name),
            walk_time_min=t.walk_time_min,
            nearest_metro_station=_strip_provenance(t.nearest_metro_station),
            bus_lines_serving=_strip_provenance(t.bus_lines_serving),
            bike_lane_nearby=t.bike_lane_nearby,
            gbfs_dock_description=tr(
                "transit_access", t.id, "gbfs_dock_description", _strip_provenance(t.gbfs_dock_description),
            ),
            transit_notes=tr("transit_access", t.id, "transit_notes", _strip_provenance(t.transit_notes)),
        )
        for t in venue.transit_accesses
    ]

    curb = [
        CurbOut(
            id=c.id,
            rideshare_zone_description=tr(
                "curb_dropoff", c.id, "rideshare_zone_description",
                _strip_provenance(c.rideshare_zone_description),
            ),
            rideshare_zone_open_window=tr(
                "curb_dropoff", c.id, "rideshare_zone_open_window",
                _strip_provenance(c.rideshare_zone_open_window),
            ),
            taxi_accessible_zone=tr(
                "curb_dropoff", c.id, "taxi_accessible_zone", _strip_provenance(c.taxi_accessible_zone),
            ),
            private_vehicle_dropoff=tr(
                "curb_dropoff", c.id, "private_vehicle_dropoff", _strip_provenance(c.private_vehicle_dropoff),
            ),
            no_stop_zones=tr("curb_dropoff", c.id, "no_stop_zones", _strip_provenance(c.no_stop_zones)),
            curbside_restrictions=tr(
                "curb_dropoff", c.id, "curbside_restrictions", _strip_provenance(c.curbside_restrictions),
            ),
        )
        for c in venue.curb_dropoffs
    ]

    cong: CongestionOut | None = None
    if venue.congestion_tdm:
        td = venue.congestion_tdm
        cong = CongestionOut(
            id=td.id,
            recommended_arrival_hrs_before_min=_float(td.recommended_arrival_hrs_before_min),
            recommended_arrival_hrs_before_max=_float(td.recommended_arrival_hrs_before_max),
            arrival_notes=tr("congestion_tdm", td.id, "arrival_notes", _strip_provenance(td.arrival_notes)),
            high_congestion_entry_roads=tr(
                "congestion_tdm", td.id, "high_congestion_entry_roads",
                _strip_provenance(td.high_congestion_entry_roads),
            ),
            known_congestion_exit_roads=tr(
                "congestion_tdm", td.id, "known_congestion_exit_roads",
                _strip_provenance(td.known_congestion_exit_roads),
            ),
            general_tdm_notes=tr(
                "congestion_tdm", td.id, "general_tdm_notes", _strip_provenance(td.general_tdm_notes),
            ),
        )

    return VenueDetailOut(
        id=venue.id,
        name=venue.name,
        sport_use=venue.sport_use,
        zone=venue.zone,
        address=venue.address,
        lat=_float(venue.lat),
        lng=_float(venue.lng),
        total_spaces=venue.total_spaces,
        total_lots=venue.total_lots,
        capacity_text=tr("venue", venue.id, "capacity_text", _strip_provenance(venue.capacity_text)),
        games_time_access_notes=tr(
            "venue", venue.id, "games_time_access_notes", _strip_provenance(venue.games_time_access_notes),
        ),
        # Inject program-level constant — not stored per-venue in the DB.
        games_time_parking_policy=GAMES_TIME_PARKING_POLICY,
        parking_options=parking,
        transit_accesses=transit,
        curb_dropoffs=curb,
        congestion_tdm=cong,
    )
