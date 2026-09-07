"""
CLI for Tier-1 automated venue enrichment (GTFS + GBFS + OSM + computed cost).

    python -m app.enrich_venue <venue_id> [<venue_id> ...]
    python -m app.enrich_venue --all

Idempotent — see app/services/venue_enrichment.py's module docstring for
what "idempotent" means here (upsert by external_ref, hand-collected rows
never touched).

Requires the GTFS static mirror tables to already be populated —
run `python -m app.ingest.gtfs_static` first if gtfs_stop is empty.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models.venue import Venue
from app.services.venue_enrichment import EnrichmentResult, enrich_venue


def _run_one(db: Session, venue: Venue) -> EnrichmentResult | None:
    try:
        result = enrich_venue(db, venue)
    except ValueError as exc:
        print(f"  SKIPPED venue {venue.id} ({venue.name}): {exc}", file=sys.stderr)
        return None
    print(
        f"  venue {result.venue_id} ({venue.name}): "
        f"{result.stops_found} stop(s), {result.rows_created} created / {result.rows_updated} updated, "
        f"{result.micromobility_count} micromobility item(s) nearby"
        + (f" — {len(result.errors)} feed error(s): {result.errors}" if result.errors else "")
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Tier-1 automated venue enrichment.")
    parser.add_argument("venue_ids", nargs="*", type=int, help="Venue id(s) to enrich")
    parser.add_argument("--all", action="store_true", help="Enrich every venue with coordinates")
    args = parser.parse_args()

    if not args.all and not args.venue_ids:
        parser.error("pass one or more venue_ids, or --all")

    with Session(engine) as db:
        if args.all:
            venues = db.execute(
                select(Venue).where(Venue.lat.is_not(None), Venue.lng.is_not(None))
            ).scalars().all()
        else:
            venues = db.execute(select(Venue).where(Venue.id.in_(args.venue_ids))).scalars().all()
            found_ids = {v.id for v in venues}
            for missing in set(args.venue_ids) - found_ids:
                print(f"  SKIPPED venue {missing}: not found", file=sys.stderr)

        if not venues:
            print("No venues to enrich.")
            return

        print(f"Enriching {len(venues)} venue(s)…")
        results = [r for v in venues if (r := _run_one(db, v)) is not None]
        db.commit()

    total_created = sum(r.rows_created for r in results)
    total_updated = sum(r.rows_updated for r in results)
    print(f"Done. {len(results)} venue(s) enriched, {total_created} row(s) created, {total_updated} updated.")


if __name__ == "__main__":
    main()
