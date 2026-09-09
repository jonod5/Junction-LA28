"""
Tier-2 LLM-assisted venue-data extraction — parking / curb-dropoff /
congestion prose fields, drafted from a venue's source pages.

This is the extraction half of the review-queue pipeline; the other half
(app/routers/venue_review.py) is what actually copies a draft into
ParkingOption / CurbDropoff / CongestionTdm, and only after a human signs
off. Nothing in this module writes to those tables — see VenueExtraction's
docstring in app/models/venue.py.

Ground rule: the model must not invent values. It's instructed to quote the
exact supporting text for every field it extracts, and to omit a field
entirely (not guess, not return null-with-a-value) when the source doesn't
support it. A field with no quote is dropped here before it ever reaches
the database — see _validate_field().

Only the prose fields are in scope, matching the pipeline prompt's own
framing ("parking, curb/drop-off, congestion"). Structured fields (prices,
booleans, hour ranges) stay Tier-1/hand-collected — free-text extraction
has no reliable way to cite a specific number as "the" price when a page
lists several by event type, and getting that wrong is a worse failure mode
than just not attempting it.

Re-running extract_venue() for a venue clears that venue's still-pending
drafts first and writes fresh ones — a re-run replaces the draft, it
doesn't pile up duplicates alongside it. Already-reviewed rows (approved /
edited / rejected) are untouched; they're the audit trail.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import get_redis
from app.models.venue import Venue, VenueExtraction

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("VENUE_EXTRACT_MODEL", "claude-sonnet-5")
PAGE_CACHE_TTL_S = 24 * 3600
# Bounds the prompt, not a content judgement — pages are HTML with a lot of
# nav/footer noise; the logistics info this pipeline wants is almost always
# well within the first ~15k characters of stripped text.
MAX_PAGE_CHARS = 15_000

# The only fields Tier-2 is allowed to draft — prose fields, one "general"
# row per venue for each entity_type. See module docstring for why
# structured/numeric fields are excluded.
FIELD_SPEC: dict[str, list[str]] = {
    "parking_option": ["price_notes", "pricing_basis", "surge_notes", "notes"],
    "curb_dropoff": [
        "rideshare_zone_description", "rideshare_zone_open_window", "taxi_accessible_zone",
        "private_vehicle_dropoff", "no_stop_zones", "curbside_restrictions",
    ],
    "congestion_tdm": [
        "arrival_notes", "high_congestion_entry_roads", "known_congestion_exit_roads", "general_tdm_notes",
    ],
}

_SYSTEM_PROMPT = f"""You extract structured venue-logistics facts from a source web page for a \
trip-planning app. You must NEVER invent or infer a value that isn't directly stated in the \
provided page text. For every field you extract, quote the exact sentence(s) from the page text \
that support it. If a field isn't covered by the page text, omit it from your output entirely — \
do not guess, do not fill in typical/default values, do not return it with an empty or null value.

Respond with a JSON object only, no prose before or after, shaped exactly like:
{{"fields": [{{"entity_type": "...", "field_name": "...", "value": "...", "quote": "...", "confidence": 0.0}}]}}

confidence is your own 0.0-1.0 estimate of how clearly the quoted text supports the value.

Valid (entity_type, field_name) pairs — only use these, and only fields the page actually supports:
{json.dumps(FIELD_SPEC, indent=2)}"""


class ExtractionError(Exception):
    """Extraction couldn't run — bad config, unreachable page, or a malformed model response."""


def _normalize_url(url: str) -> str:
    # VenueSource.primary_url/secondary_url were collected as human-readable
    # citations, not machine-fetchable links — several are bare domains
    # like "lacoliseum.com/" with no scheme, which httpx rejects outright.
    return url if re.match(r"^https?://", url) else f"https://{url}"


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_PAGE_CHARS]


def _fetch_page(url: str) -> str:
    url = _normalize_url(url)
    r = get_redis()
    key = f"venue_extract:page:{url}"
    cached = r.get(key)
    if cached is not None:
        return cached

    # Same rationale as app/ingest/osm.py's Overpass fix — a generic
    # User-Agent gets blocked by some sites' bot filtering.
    headers = {"User-Agent": "junction-la28-venue-extraction/1.0 (github.com/jonod5/Junction-LA28)"}
    with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    text = _strip_html(resp.text)
    r.setex(key, PAGE_CACHE_TTL_S, text)
    return text


def _llm_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExtractionError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=api_key)


def _extract_fields_from_page(page_text: str, url: str) -> list[dict]:
    client = _llm_client()
    resp = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Source URL: {url}\n\nPage text:\n{page_text}"}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("fields"), list):
        raise ExtractionError("model response missing a 'fields' list")
    return parsed["fields"]


def _validate_field(raw: dict) -> dict | None:
    """None means "drop this" — either it's outside FIELD_SPEC, or the model
    didn't back it with a value + quote (which we treat as it declining to
    extract, exactly the behavior the system prompt asks for)."""
    entity_type, field_name = raw.get("entity_type"), raw.get("field_name")
    allowed = FIELD_SPEC.get(entity_type)
    if not allowed or field_name not in allowed:
        log.warning("Dropping extracted field outside FIELD_SPEC: %s.%s", entity_type, field_name)
        return None
    value, quote = raw.get("value"), raw.get("quote")
    if not value or not quote or not str(value).strip() or not str(quote).strip():
        return None
    confidence = raw.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return {
        "entity_type": entity_type,
        "field_name": field_name,
        "value": str(value).strip(),
        "quote": str(quote).strip(),
        "confidence": confidence,
    }


# VenueSource.primary_url/secondary_url were hand-collected as human-readable
# citations, not clean machine links — real values in this codebase include
# bare domains with no scheme, multiple URLs in one string (newline- or
# "and"-separated), and trailing prose ("(official venue site, event page
# dated ...)"). This pulls out just the URL-shaped substrings, in order,
# ignoring everything else — a trailing parenthetical never gets glued onto
# the path because "(" and ")" and whitespace all end a match.
_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[a-zA-Z0-9][\w-]*(?:\.[a-zA-Z0-9][\w-]*)*\.[a-zA-Z]{2,}(?:/[^\s()]*)?")


def source_urls_for(venue: Venue) -> list[str]:
    urls: list[str] = []
    for s in venue.sources:
        for raw in (s.primary_url, s.secondary_url):
            if not raw:
                continue
            for match in _URL_RE.findall(raw):
                url = _normalize_url(match)
                if url not in urls:
                    urls.append(url)
    return urls


@dataclass
class ExtractionResult:
    venue_id: int
    urls_processed: int
    fields_drafted: int
    errors: list[str] = field(default_factory=list)


def extract_venue(db: Session, venue: Venue, urls: list[str] | None = None) -> ExtractionResult:
    """
    Fetch each of the venue's source URLs, ask the model to extract
    supported prose fields with citations, and write pending
    VenueExtraction rows. Never touches ParkingOption / CurbDropoff /
    CongestionTdm.
    """
    source_urls = urls if urls is not None else source_urls_for(venue)
    if not source_urls:
        raise ValueError(f"Venue {venue.id} has no source URLs to extract from")

    errors: list[str] = []
    drafts: list[dict] = []

    for url in source_urls:
        try:
            page_text = _fetch_page(url)
        except httpx.HTTPError as exc:
            errors.append(f"fetch {url}: {exc}")
            continue

        try:
            raw_fields = _extract_fields_from_page(page_text, url)
        except (ExtractionError, anthropic.APIError) as exc:
            errors.append(f"extract {url}: {exc}")
            continue

        for raw in raw_fields:
            valid = _validate_field(raw)
            if valid:
                valid["source_url"] = url
                drafts.append(valid)

    # A re-run replaces the outstanding draft rather than piling up
    # duplicates next to it. Reviewed rows (approved/edited/rejected) are
    # this table's audit trail and are never touched here.
    for stale in db.execute(
        select(VenueExtraction).where(VenueExtraction.venue_id == venue.id, VenueExtraction.status == "pending")
    ).scalars().all():
        db.delete(stale)
    db.flush()

    now = datetime.now(timezone.utc)
    for d in drafts:
        db.add(VenueExtraction(
            venue_id=venue.id,
            entity_type=d["entity_type"],
            field_name=d["field_name"],
            extracted_value=d["value"],
            source_url=d["source_url"],
            source_quote=d["quote"],
            confidence=d["confidence"],
            status="pending",
            created_at=now,
        ))

    return ExtractionResult(
        venue_id=venue.id, urls_processed=len(source_urls), fields_drafted=len(drafts), errors=errors,
    )
