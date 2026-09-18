"""
CLI for Tier-2 LLM-assisted venue-data extraction.

    python -m app.extract_venue <venue_id> [<venue_id> ...]
    python -m app.extract_venue --all

Reads each venue's source URLs from its VenueSource rows (primary_url /
secondary_url) — the same table the original hand-collection already
populated, so a venue only needs sources added once. Requires
ANTHROPIC_API_KEY to be set.

This only drafts rows into the review queue (venue_extraction) — nothing it
does is visible to the consumer app until a human approves it via the
review-queue API (app/routers/venue_review.py). See
app/services/venue_extract.py's module docstring for the full pipeline.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models.venue import Venue
from app.services.venue_extract import ExtractionResult, extract_venue


def _run_one(db: Session, venue: Venue) -> ExtractionResult | None:
    try:
        result = extract_venue(db, venue)
    except ValueError as exc:
        print(f"  SKIPPED venue {venue.id} ({venue.name}): {exc}", file=sys.stderr)
        return None
    print(
        f"  venue {result.venue_id} ({venue.name}): "
        f"{result.urls_processed} url(s) processed, {result.fields_drafted} new field(s), "
        f"{result.changes_flagged} change(s) flagged for review"
        + (f" — {len(result.errors)} error(s): {result.errors}" if result.errors else "")
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Tier-2 LLM-assisted venue-data extraction.")
    parser.add_argument("venue_ids", nargs="*", type=int, help="Venue id(s) to extract")
    parser.add_argument("--all", action="store_true", help="Extract every venue that has source URLs")
    args = parser.parse_args()
    if not args.all and not args.venue_ids:
        parser.error("pass one or more venue_ids, or --all")

    with Session(engine) as db:
        if args.all:
            venues = db.execute(select(Venue)).scalars().all()
        else:
            venues = db.execute(select(Venue).where(Venue.id.in_(args.venue_ids))).scalars().all()
            found_ids = {v.id for v in venues}
            for missing in set(args.venue_ids) - found_ids:
                print(f"  SKIPPED venue {missing}: not found", file=sys.stderr)

        if not venues:
            print("No venues to extract.")
            return

        print(f"Extracting {len(venues)} venue(s)…")
        results = [r for v in venues if (r := _run_one(db, v)) is not None]
        db.commit()

    total_fields = sum(r.fields_drafted for r in results)
    total_changes = sum(r.changes_flagged for r in results)
    print(
        f"Done. {len(results)} venue(s) processed, {total_fields} new field(s) and "
        f"{total_changes} change(s) awaiting review."
    )


if __name__ == "__main__":
    main()
