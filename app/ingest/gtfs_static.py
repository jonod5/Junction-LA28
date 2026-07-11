"""
GTFS static ingest — download, parse, and bulk-load into mirror tables.

Usage (run once per feed update):
    python -m app.ingest.gtfs_static

Supports multiple feeds via a comma-separated GTFS_STATIC_URLS env var.
All feeds are merged into the same four mirror tables in one transaction —
tables are truncated once at the start, then each feed is appended.

LA Metro publishes two separate zips:
  Rail: https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip
  Bus:  https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip
Rail and bus use non-overlapping route_id/trip_id namespaces so merging is
safe without any prefix logic.  stop_id CAN overlap (the same physical stop
may appear in both feeds); duplicates are deduplicated by stop_id before
inserting so the primary-key constraint is never violated.

Design choices:
- SQLAlchemy Core bulk inserts (not ORM) — bus stop_times alone can be 3M+
  rows; ORM object construction would be ~10× slower.
- Streams each zip from the URL so we never write multi-MB files to disk.
- CSV parsing uses the stdlib csv module — no pandas dependency.
"""

import csv
import io
import logging
import os
import zipfile
from urllib.request import urlopen

from sqlalchemy import delete, insert, text

from app.db import engine
from app.models.gtfs import GtfsRoute, GtfsStop, GtfsStopTime, GtfsTrip

log = logging.getLogger(__name__)

BATCH_SIZE = 5_000  # rows per INSERT batch; tune for your DB server


def _download_zip(url: str) -> zipfile.ZipFile:
    log.info("Downloading GTFS feed from %s", url)
    with urlopen(url) as response:  # noqa: S310 — URL comes from trusted env var
        data = response.read()
    return zipfile.ZipFile(io.BytesIO(data))


def _csv_rows(zf: zipfile.ZipFile, filename: str) -> list[dict]:
    try:
        with zf.open(filename) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            return list(reader)
    except KeyError:
        log.warning("%s not found in GTFS zip — skipping", filename)
        return []


def _insert_batches(conn, table_insert, rows: list[dict]) -> int:
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        conn.execute(table_insert, batch)
        total += len(batch)
    return total


def _parse_stops(zf: zipfile.ZipFile) -> list[dict]:
    return [
        {
            "stop_id": r["stop_id"],
            "stop_name": r.get("stop_name"),
            "stop_lat": r.get("stop_lat") or None,
            "stop_lon": r.get("stop_lon") or None,
            "stop_desc": r.get("stop_desc") or None,
            "zone_id": r.get("zone_id") or None,
            "location_type": (
                int(r["location_type"]) if r.get("location_type") else None
            ),
            "parent_station": r.get("parent_station") or None,
        }
        for r in _csv_rows(zf, "stops.txt")
    ]


def _parse_routes(zf: zipfile.ZipFile) -> list[dict]:
    return [
        {
            "route_id": r["route_id"],
            "agency_id": r.get("agency_id") or None,
            "route_short_name": r.get("route_short_name") or None,
            "route_long_name": r.get("route_long_name") or None,
            "route_type": (
                int(r["route_type"]) if r.get("route_type") else None
            ),
            "route_color": r.get("route_color") or None,
            "route_text_color": r.get("route_text_color") or None,
        }
        for r in _csv_rows(zf, "routes.txt")
    ]


def _parse_trips(zf: zipfile.ZipFile) -> list[dict]:
    return [
        {
            "trip_id": r["trip_id"],
            "route_id": r.get("route_id") or None,
            "service_id": r.get("service_id") or None,
            "trip_headsign": r.get("trip_headsign") or None,
            "direction_id": (
                int(r["direction_id"]) if r.get("direction_id") else None
            ),
            "shape_id": r.get("shape_id") or None,
        }
        for r in _csv_rows(zf, "trips.txt")
    ]


def _stream_stop_times(conn, zf: zipfile.ZipFile) -> int:
    """Stream stop_times directly from the zip into the DB in batches."""
    total = 0
    try:
        with zf.open("stop_times.txt") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
            batch: list[dict] = []
            for row in reader:
                batch.append(
                    {
                        "trip_id": row["trip_id"],
                        "stop_id": row["stop_id"],
                        "arrival_time": row.get("arrival_time") or None,
                        "departure_time": row.get("departure_time") or None,
                        "stop_sequence": (
                            int(row["stop_sequence"])
                            if row.get("stop_sequence")
                            else None
                        ),
                        "stop_headsign": row.get("stop_headsign") or None,
                        "pickup_type": (
                            int(row["pickup_type"])
                            if row.get("pickup_type")
                            else None
                        ),
                        "drop_off_type": (
                            int(row["drop_off_type"])
                            if row.get("drop_off_type")
                            else None
                        ),
                    }
                )
                if len(batch) >= BATCH_SIZE:
                    conn.execute(insert(GtfsStopTime), batch)
                    total += len(batch)
                    batch = []
            if batch:
                conn.execute(insert(GtfsStopTime), batch)
                total += len(batch)
    except KeyError:
        log.warning("stop_times.txt not found in zip — skipping")
    return total


def run(urls: list[str] | None = None) -> None:
    """
    Load one or more GTFS feeds into the mirror tables.

    `urls` defaults to the comma-separated GTFS_STATIC_URLS env var
    (falls back to GTFS_STATIC_URL for backwards compatibility).
    """
    if urls is None:
        raw = os.environ.get("GTFS_STATIC_URLS") or os.environ["GTFS_STATIC_URL"]
        urls = [u.strip() for u in raw.split(",") if u.strip()]

    log.info("Ingesting %d GTFS feed(s): %s", len(urls), urls)

    # Download all zips before touching the DB so a bad URL doesn't leave
    # the tables half-truncated.
    zips = [_download_zip(url) for url in urls]

    # Collect and deduplicate stops and routes across all feeds.
    # stop_id PK: rail and bus can share physical stops — keep first seen.
    # route_id PK: rail and bus use non-overlapping namespaces in LA Metro.
    all_stops: dict[str, dict] = {}
    all_routes: dict[str, dict] = {}
    all_trips: dict[str, dict] = {}

    for zf in zips:
        for row in _parse_stops(zf):
            all_stops.setdefault(row["stop_id"], row)
        for row in _parse_routes(zf):
            all_routes.setdefault(row["route_id"], row)
        for row in _parse_trips(zf):
            all_trips.setdefault(row["trip_id"], row)

    with engine.begin() as conn:
        log.info("Clearing existing GTFS mirror tables…")
        conn.execute(delete(GtfsStopTime))
        conn.execute(delete(GtfsTrip))
        conn.execute(delete(GtfsRoute))
        conn.execute(delete(GtfsStop))

        n = _insert_batches(conn, insert(GtfsStop), list(all_stops.values()))
        log.info("Inserted %d stops", n)

        n = _insert_batches(conn, insert(GtfsRoute), list(all_routes.values()))
        log.info("Inserted %d routes", n)

        n = _insert_batches(conn, insert(GtfsTrip), list(all_trips.values()))
        log.info("Inserted %d trips", n)

        log.info("Loading stop_times from %d feed(s)…", len(zips))
        total_st = sum(_stream_stop_times(conn, zf) for zf in zips)
        log.info("Inserted %d stop_times total", total_st)

        # Reset the autoincrement sequence after bulk insert (Postgres only).
        conn.execute(
            text(
                "SELECT setval('gtfs_stop_time_id_seq', "
                "(SELECT MAX(id) FROM gtfs_stop_time))"
            )
        )

    log.info("GTFS static ingest complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
