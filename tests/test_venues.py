"""
Venue detail API — provenance stripping.

The venue-collection notes were hand-written with inline citation asides
mixed directly into the prose (e.g. "Walk time (own research): 6 mins").
These tests use real strings pulled from app/seed_venues.py so the fix is
checked against the actual dataset, not just synthetic examples.
"""

import os

# app.db reads DATABASE_URL at import time; app.routers.venues imports
# app.db transitively.  Set a dummy value before the import — SQLAlchemy is
# lazy on connect, so no real DB is ever touched by these pure-function tests.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.routers.venues import _strip_provenance  # noqa: E402


def test_strips_own_research_tag():
    text = "Walk times (own research): Expo Park/USC Station (6 mins); Expo/Vermont Station (6 mins)."
    cleaned = _strip_provenance(text)
    assert "own research" not in cleaned.lower()
    # The actual data — station names and minute counts — must survive.
    assert "Expo Park/USC Station" in cleaned
    assert "6 mins" in cleaned


def test_strips_per_source_citation():
    text = "Nearest Metro station: Chinatown Station (A/E Line via Pico Station, per Metro's own blog)."
    cleaned = _strip_provenance(text)
    assert "per" not in cleaned.lower()
    assert "Chinatown Station" in cleaned


def test_strips_pdf_citation():
    text = "Closest lot to venue entrance (lacoliseum.com, 2023 PDF, lot names): Lot 1; Lot W."
    cleaned = _strip_provenance(text)
    assert "PDF" not in cleaned
    assert "Lot 1" in cleaned


def test_strips_unverified_and_editorial_aside():
    # Real shape from the seed data: the citation + editorial aside is itself
    # inside the parenthetical, not loose in the sentence.
    text = (
        "Recommended arrival (per an unverified 2-year-old Reddit comment about a "
        "different event — flagging the discrepancy) is 90 minutes."
    )
    cleaned = _strip_provenance(text)
    assert "unverified" not in cleaned.lower()
    assert "Reddit" not in cleaned
    assert "90 minutes" in cleaned


def test_strips_not_verified_officially():
    text = "SoFi lot count: 28 lots per venue signage (not verified officially)."
    cleaned = _strip_provenance(text)
    assert "not verified" not in cleaned.lower()
    assert "28 lots" in cleaned


def test_leaves_plain_english_per_untouched_outside_parens():
    # "per" used in its ordinary English sense (not inside a parenthetical
    # citation) must survive — only the parenthetical form is provenance.
    text = 'Coliseum ADA page states "Event parking rates may vary per event."'
    assert _strip_provenance(text) == text


def test_leaves_genuine_data_parentheticals_alone():
    # Parentheticals that are just data (a duration, a cross-street) must
    # survive untouched — only citation/verification asides are stripped.
    text = "Walk time from bus stop: ~1-2 Mins. Nearby cross street (Century Blvd/Florence Ave exits)."
    assert _strip_provenance(text) == text


def test_strips_leading_own_research_label():
    text = "Own research: No scooter/dock zones nearby"
    cleaned = _strip_provenance(text)
    assert "own research" not in cleaned.lower()
    assert cleaned == "No scooter/dock zones nearby"


def test_strips_reddit_citation_sentence_keeps_rest():
    text = (
        "Pricing is event-specific and set per event (confirmed different rate for the general "
        "public event-parking portal vs. UCLA Football portal). "
        "A Reddit mention (not verified officially) cited $33 lot pricing for a 2025 concert — "
        "flagging as unverified rather than treating as fact."
    )
    cleaned = _strip_provenance(text)
    assert "reddit" not in cleaned.lower()
    assert "unverified" not in cleaned.lower()
    # The genuine pricing-scheme info in the first sentence must survive.
    assert "event-specific" in cleaned
    assert "UCLA Football portal" in cleaned


def test_strips_whole_field_no_data_placeholder():
    # arrival_notes for the Coliseum is literally this — a research
    # placeholder meaning "no value found," not real arrival guidance.
    assert _strip_provenance("not stated in source") is None


def test_strips_whole_field_not_stated():
    # private_vehicle_dropoff for Crypto.com Arena is literally this.
    assert _strip_provenance("Not stated") is None


def test_handles_none_and_empty():
    assert _strip_provenance(None) is None
    assert _strip_provenance("") is None


def test_collapses_whitespace_left_by_removal():
    text = "Bike lane nearby (own research)  ; bicycle parking available."
    cleaned = _strip_provenance(text)
    assert "  " not in cleaned
    assert cleaned.startswith("Bike lane nearby")
