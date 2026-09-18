"""
ORM models mirroring the five sections of the Venue Data Collection sheet:
  1. Venue             — core identity + venue-level parking capacity
  2. ParkingOption     — § Parking (one row per lot / zone)
  3. CurbDropoff       — § Curb & Pickup/Drop-off
  4. TransitAccess     — § Transit Access
  5. CongestionTdm     — § Congestion & TDM
  6. VenueSource       — § Sources & Verification (one row per venue)

No values are seeded here — see app/seed_venues.py.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# ---------------------------------------------------------------------------
# Program-level constant — applies equally to all LA28 venues.
# Store here, NOT as a DB column; all venues share the same policy.
# ---------------------------------------------------------------------------
GAMES_TIME_PARKING_POLICY = (
    "No spectator parking at venues during LA28 Games. "
    "Attendees must use transit, sanctioned park-and-ride, or active transport."
)


class Venue(Base):
    __tablename__ = "venue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sport_use: Mapped[str | None] = mapped_column(String(200))
    zone: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    # Venue-level parking capacity (from "Total parking spaces" / "Total parking lots" rows)
    total_spaces: Mapped[int | None] = mapped_column(Integer)
    total_lots: Mapped[int | None] = mapped_column(Integer)
    capacity_text: Mapped[str | None] = mapped_column(Text)  # raw phrase from doc

    # Venue-specific Games-time shuttle / park-and-ride logistics (LA28-specific)
    games_time_access_notes: Mapped[str | None] = mapped_column(Text)

    # Collection metadata
    collection_status: Mapped[str | None] = mapped_column(String(50))
    date_collected: Mapped[date | None] = mapped_column(Date)
    data_sources_summary: Mapped[str | None] = mapped_column(Text)

    # ── Automated pipeline provenance (v1.7 Tier-1/2) ──────────────────────
    # Tracks whether THIS PIPELINE has run for this venue and had its
    # output reviewed — distinct from the venue's overall data quality.
    # The 6 original hand-collected venues default to reviewed=False here
    # too (they predate this pipeline and were never run through it) — that
    # does NOT mean their existing data is untrusted; nothing gates venue
    # visibility on this column. See app/services/venue_enrichment.py's
    # module docstring for the tier model this supports.
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(20))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Gold-standard flag (v1.7 Phase 3) ───────────────────────────────────
    # Marks the hand-collected venues app/validate_pipeline.py checks the
    # pipeline's output against. Set once at collection time, not something
    # the pipeline itself ever writes.
    is_gold_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    parking_options: Mapped[list["ParkingOption"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    curb_dropoffs: Mapped[list["CurbDropoff"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    transit_accesses: Mapped[list["TransitAccess"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    congestion_tdm: Mapped["CongestionTdm | None"] = relationship(
        back_populates="venue", cascade="all, delete-orphan", uselist=False
    )
    sources: Mapped[list["VenueSource"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    extractions: Mapped[list["VenueExtraction"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    games_time_official: Mapped["GamesTimeOfficial | None"] = relationship(
        back_populates="venue", cascade="all, delete-orphan", uselist=False
    )


class ParkingOption(Base):
    """One row per lot / zone."""

    __tablename__ = "parking_option"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    lot_name: Mapped[str | None] = mapped_column(Text)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)

    # Numeric price envelope (lowest / highest across all event types and purchase timing)
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    # Full event-type / advance-vs-gate breakdown verbatim from doc
    price_notes: Mapped[str | None] = mapped_column(Text)
    # Provenance caveat — e.g. "UCLA Football 11/8/2025 — not confirmed LA28 Olympic pricing"
    pricing_basis: Mapped[str | None] = mapped_column(Text)

    has_surge_pricing: Mapped[bool | None] = mapped_column(Boolean)
    surge_notes: Mapped[str | None] = mapped_column(Text)
    is_closest_to_entrance: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    # ── Automated pipeline provenance (v1.7 Phase 2) ────────────────────────
    # Set when a Tier-2 extraction is approved into this row (see
    # app/routers/venue_review.py) — never set by extraction itself, which
    # only ever writes to VenueExtraction. See that model's docstring.
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(20))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    venue: Mapped["Venue"] = relationship(back_populates="parking_options")


class CurbDropoff(Base):
    __tablename__ = "curb_dropoff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    rideshare_zone_description: Mapped[str | None] = mapped_column(Text)
    rideshare_zone_open_window: Mapped[str | None] = mapped_column(String(200))
    taxi_accessible_zone: Mapped[str | None] = mapped_column(Text)
    private_vehicle_dropoff: Mapped[str | None] = mapped_column(Text)
    no_stop_zones: Mapped[str | None] = mapped_column(Text)
    curbside_restrictions: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    # ── Automated pipeline provenance (v1.7 Phase 2) — see ParkingOption ───
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(20))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    venue: Mapped["Venue"] = relationship(back_populates="curb_dropoffs")


class TransitAccess(Base):
    __tablename__ = "transit_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    line: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(String(50))
    stop_name: Mapped[str | None] = mapped_column(Text)
    walk_time_min: Mapped[int | None] = mapped_column(Integer)

    nearest_metro_station: Mapped[str | None] = mapped_column(Text)
    bus_lines_serving: Mapped[str | None] = mapped_column(Text)
    bike_lane_nearby: Mapped[bool | None] = mapped_column(Boolean)
    gbfs_dock_description: Mapped[str | None] = mapped_column(Text)
    transit_notes: Mapped[str | None] = mapped_column(Text)
    # Modeled ride-hail cost for this same trip (venue <-> this stop), from
    # app.services.fares — a comparison point next to the transit option,
    # not a quote. NULL for hand-collected rows, which never computed one.
    rideshare_estimate_usd: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    source: Mapped[str] = mapped_column(String(500), nullable=False)
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    # ── Automated pipeline provenance (v1.7 Tier-1/2) ──────────────────────
    # external_ref stores the upstream feed's stable id (e.g. a GTFS
    # stop_id) for rows this pipeline created — the key re-enrichment runs
    # match against to update in place instead of duplicating, and that
    # Phase 3's change detection diffs against. NULL for hand-collected rows.
    external_ref: Mapped[str | None] = mapped_column(String(100))
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(20))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    venue: Mapped["Venue"] = relationship(back_populates="transit_accesses")


class CongestionTdm(Base):
    """One row per venue (1-to-1)."""

    __tablename__ = "congestion_tdm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Arrival time envelope — overall min/max across all lot types / event types
    recommended_arrival_hrs_before_min: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    recommended_arrival_hrs_before_max: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    # Authoritative detail: lot vs gate vs shuttle, per event type, verbatim from doc
    arrival_notes: Mapped[str | None] = mapped_column(Text)

    high_congestion_entry_roads: Mapped[str | None] = mapped_column(Text)
    known_congestion_exit_roads: Mapped[str | None] = mapped_column(Text)
    event_day_parking_surge: Mapped[bool | None] = mapped_column(Boolean)
    past_congestion_refs: Mapped[str | None] = mapped_column(Text)
    general_tdm_notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str | None] = mapped_column(String(500))
    date_collected: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    data_gaps: Mapped[str | None] = mapped_column(Text)

    # ── Automated pipeline provenance (v1.7 Phase 2) — see ParkingOption ───
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)
    confidence: Mapped[str | None] = mapped_column(String(20))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    venue: Mapped["Venue"] = relationship(back_populates="congestion_tdm")


class VenueSource(Base):
    """One row per venue — primary and secondary source URLs."""

    __tablename__ = "venue_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    primary_url: Mapped[str | None] = mapped_column(Text)
    secondary_url: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[str | None] = mapped_column(String(50))
    verified_at: Mapped[date | None] = mapped_column(Date)

    venue: Mapped["Venue"] = relationship(back_populates="sources")


class VenueExtraction(Base):
    """
    The review queue — one row per (venue, field) drafted either by Tier-2
    extraction (app.services.venue_extract, from a source page) or by
    Tier-1 change detection (app.services.venue_enrichment, when a re-run's
    freshly-computed GTFS/GBFS/OSM values differ from what's stored). This
    table is the ONLY thing either writes to; nothing here is treated as
    fact until a human decision via app/routers/venue_review.py copies a
    value into ParkingOption / CurbDropoff / CongestionTdm / TransitAccess
    (approve, or edit then approve). Rejected and approved rows are kept as
    history, not deleted — this table IS the audit trail.

    entity_type is which table the field belongs to ("parking_option" /
    "curb_dropoff" / "congestion_tdm" / "transit_access") — and, given the
    current pipeline, also tells you which tier drafted it: transit_access
    only ever comes from Tier-1, the other three only ever from Tier-2.

    Two shapes of draft, distinguished by status and previous_value:
      - status="pending", previous_value=None — a field with no existing
        value. entity_id is usually None too (see
        app/services/venue_targets.py — parking_option/curb_dropoff/
        congestion_tdm resolve their target row lazily, since it may not
        exist yet; transit_access always has one, because Tier-1 change
        detection only runs against a row that already exists).
      - status="pending_change", previous_value=<the stored value> — a
        field that already has a value, and the pipeline computed a
        different one. Approving this REPLACES the old value (unlike a
        plain "pending" draft, which is refused if the field somehow
        already has one) — see app/routers/venue_review.py's staleness
        check, which re-verifies the field still equals previous_value at
        decision time before applying.

    source_quote is the exact supporting text the LLM was instructed to
    cite for extracted_value, for Tier-2 drafts — see
    app/services/venue_extract.py's system prompt. Tier-1 drafts have no
    prose to quote and leave it NULL; source_url is used loosely there too,
    holding the pipeline's feed-provenance string (e.g.
    "gtfs_static+directions_api") rather than a literal URL.
    """

    __tablename__ = "venue_extraction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )

    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # The specific target row, when known at draft time — see class
    # docstring. NULL means "resolve it when a decision is applied."
    entity_id: Mapped[int | None] = mapped_column(Integer)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    extracted_value: Mapped[str] = mapped_column(Text, nullable=False)
    # The value this draft proposes to replace — NULL for a brand-new
    # field. See class docstring's "two shapes of draft."
    previous_value: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_quote: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    # pending | pending_change -> approved | edited | rejected | superseded
    # (a later draft for the same venue/entity_type/field_name was decided
    # first — see app/routers/venue_review.py's decision endpoint).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    corrected_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[str | None] = mapped_column(String(100))

    venue: Mapped["Venue"] = relationship(back_populates="extractions")


class GamesTimeOfficial(Base):
    """
    Tier-3 scaffold — one row per venue for Games-time official LA28 data
    (car-restricted zones, designated PUDO, shuttles, arrival windows).
    Nothing populates these fields yet; this table exists so the app can
    transparently show "awaiting official LA28 data" rather than nothing
    at all. source defaults to "official_pending" and stays that way until
    a real ingestion path exists — do not populate or invent values here.
    """

    __tablename__ = "games_time_official"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    car_restricted_zones: Mapped[str | None] = mapped_column(Text)
    designated_pudo: Mapped[str | None] = mapped_column(Text)
    shuttles: Mapped[str | None] = mapped_column(Text)
    arrival_windows: Mapped[str | None] = mapped_column(Text)

    source: Mapped[str] = mapped_column(String(500), nullable=False, default="official_pending")
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime)

    venue: Mapped["Venue"] = relationship(back_populates="games_time_official")


class VenueTranslation(Base):
    """
    One row per (venue, entity, field, language) — a translated value for a
    single free-text column on Venue/ParkingOption/CurbDropoff/TransitAccess/
    CongestionTdm.  English itself is never stored here: it stays the system
    of record on the source tables above, and this table only holds what a
    translation *adds* (es/fr/zh-Hans), so the API can fall back to English
    whenever a row is missing.

    entity_type names the source table ("venue", "parking_option",
    "curb_dropoff", "transit_access", "congestion_tdm"); entity_id is that
    row's own primary key (for entity_type="venue", entity_id == venue_id —
    kept non-null on every row so the uniqueness constraint below actually
    holds; NULL != NULL in SQL and would otherwise let venue-level fields
    collect duplicate rows per language).

    `reviewed` defaults False: every row this app populates is a first-pass
    (machine or non-native) translation until a native speaker signs off —
    same "no unverified data shown as fact" discipline as the UI strings in
    frontend/locales/README.md. Query `reviewed=False` as the review queue.
    """

    __tablename__ = "venue_translation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    venue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("venue.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str] = mapped_column(String(50), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "field", "language",
            name="uq_venue_translation_key",
        ),
    )
