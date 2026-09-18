"""
python -m app.validate_pipeline [--venue-ids <id> ...]

QA gate + rough research metric for the venue-data pipeline (v1.7 Phase 3):
checks, read-only, whether Tier-1 and Tier-2 actually produce output for
the gold-standard hand-collected venues (Venue.is_gold_standard) — venues
we already know have real transit options and real source pages nearby.

Deliberately a coverage/sanity check, not a text-accuracy scorer: hand-
collected notes are free prose and feed/LLM output is structured or
differently worded, so exact field comparison isn't meaningful here. What
IS meaningful, and what this catches, is total pipeline failure — a feed
outage, a broken query, a prompt regression — showing up as the coverage
rate for known-good venues crashing toward 0%.

Nothing is written: Tier-1 is checked via its own read-only
find_nearest_transit()/GBFS/OSM calls rather than enrich_venue(), and
Tier-2 via the same page-fetch + extract-and-validate steps
extract_venue() uses internally, without ever adding to the session. Tier-2
checking is skipped entirely (reported, not silently omitted) when
ANTHROPIC_API_KEY isn't configured.
"""

from __future__ import annotations

import argparse
import os

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.ingest.gbfs import get_nearby as gbfs_get_nearby
from app.ingest.osm import nearby_context
from app.models.venue import Venue
from app.services.venue_enrichment import (
    DEFAULT_MICROMOBILITY_RADIUS_M,
    DEFAULT_OSM_RADIUS_M,
    find_nearest_transit,
)
from app.services.venue_extract import (
    ExtractionError,
    _extract_fields_from_page,
    _fetch_page,
    _validate_field,
    source_urls_for,
)


def _validate_tier1(db: Session, venue: Venue) -> dict:
    if venue.lat is None or venue.lng is None:
        return {"ok": False, "reason": "no coordinates"}
    lat, lng = float(venue.lat), float(venue.lng)
    stops = find_nearest_transit(db, lat, lng)
    micro = gbfs_get_nearby(lat, lng, DEFAULT_MICROMOBILITY_RADIUS_M)
    osm = nearby_context(lat, lng, DEFAULT_OSM_RADIUS_M)
    return {
        "ok": True,
        "stops_found": len(stops),
        "micromobility_found": len(micro["items"]),
        "osm_elements_found": len(osm["elements"]),
    }


def _validate_tier2(venue: Venue) -> dict:
    urls = source_urls_for(venue)
    if not urls:
        return {"ok": False, "reason": "no source URLs"}

    fields_found = 0
    errors: list[str] = []
    for url in urls:
        try:
            page_text = _fetch_page(url)
            raw_fields = _extract_fields_from_page(page_text, url)
        except (ExtractionError, anthropic.APIError, httpx.HTTPError) as exc:
            errors.append(f"{url}: {exc}")
            continue
        fields_found += sum(1 for raw in raw_fields if _validate_field(raw))

    return {"ok": True, "urls_checked": len(urls), "fields_found": fields_found, "errors": errors}


def _print_summary(label: str, results: list[tuple[Venue, dict]], key: str) -> None:
    checked = [r for _, r in results if r["ok"]]
    if not checked:
        print(f"{label}: no venues could be checked.")
        return
    produced = sum(1 for r in checked if r[key] > 0)
    pct = 100 * produced / len(checked)
    print(f"{label}: {produced}/{len(checked)} gold venue(s) ({pct:.0f}%) produced at least one result.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the venue-data pipeline against gold-standard venues.")
    parser.add_argument(
        "--venue-ids", nargs="*", type=int, dest="venue_ids",
        help="Restrict to specific gold-standard venue ids (default: all)",
    )
    args = parser.parse_args()

    tier2_configured = bool(os.environ.get("ANTHROPIC_API_KEY"))

    with Session(engine) as db:
        query = select(Venue).where(Venue.is_gold_standard.is_(True))
        if args.venue_ids:
            query = query.where(Venue.id.in_(args.venue_ids))
        venues = db.execute(query).scalars().all()

        if not venues:
            print("No gold-standard venues found.")
            return

        print(f"Validating pipeline against {len(venues)} gold-standard venue(s)…\n")

        tier1_results: list[tuple[Venue, dict]] = []
        tier2_results: list[tuple[Venue, dict]] = []

        for v in venues:
            t1 = _validate_tier1(db, v)
            tier1_results.append((v, t1))
            if t1["ok"]:
                print(
                    f"  [Tier 1] {v.name}: {t1['stops_found']} transit stop(s), "
                    f"{t1['micromobility_found']} micromobility item(s), "
                    f"{t1['osm_elements_found']} OSM context element(s)"
                )
            else:
                print(f"  [Tier 1] {v.name}: SKIPPED — {t1['reason']}")

            if tier2_configured:
                t2 = _validate_tier2(v)
                tier2_results.append((v, t2))
                if t2["ok"]:
                    print(
                        f"  [Tier 2] {v.name}: {t2['fields_found']} field(s) extractable from "
                        f"{t2['urls_checked']} url(s)"
                        + (f" — {len(t2['errors'])} error(s)" if t2["errors"] else "")
                    )
                else:
                    print(f"  [Tier 2] {v.name}: SKIPPED — {t2['reason']}")

    print()
    _print_summary("Tier 1", tier1_results, key="stops_found")
    if tier2_configured:
        _print_summary("Tier 2", tier2_results, key="fields_found")
    else:
        print("Tier 2: SKIPPED for all venues — ANTHROPIC_API_KEY is not configured.")


if __name__ == "__main__":
    main()
