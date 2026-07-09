# Integrations

_Last mapped: 2026-07-09_

## External APIs

### Google Places Text Search
- **Endpoint:** `https://maps.googleapis.com/maps/api/place/textsearch/json`
- **Auth:** `GOOGLE_MAPS_API_KEY` env var (server-side only; never exposed to clients)
- **Used by:** `app/routers/places.py` — `GET /api/places?query=`
- **Notes:** Location-biased to LA (34.0522,-118.2437), 50km radius. Returns only `name` + `address`. Redis caching planned but not yet implemented (TODO comment in code).

### LA Metro GTFS-Realtime API (JSON)
- **Endpoints:**
  - `https://api.metro.net/LACMTA/vehicle_positions/all` (bus)
  - `https://api.metro.net/LACMTA_Rail/vehicle_positions/all` (rail)
- **Auth:** Optional bearer token via `GTFS_RT_API_KEY`
- **Used by:** `app/ingest/gtfs_rt.py` → `app/routers/vehicles.py` — `GET /api/vehicles`
- **Notes:** Returns JSON (not protobuf). Results merged across both agency IDs. Cached in Redis with 30s TTL.

### LA Metro GTFS Static Feeds
- **Endpoints (defaults):**
  - Rail: `https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip`
  - Bus: `https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip`
- **Used by:** `app/ingest/gtfs_static.py` — run manually as `python -m app.ingest.gtfs_static`
- **Notes:** Downloads zips in-memory (no disk write). Bulk-loads stops/routes/trips/stop_times. Deduplicates stops by `stop_id` across feeds. Rail and bus use non-overlapping `route_id`/`trip_id` namespaces.

## Databases

### PostgreSQL 16
- Named volume `postgres_data` persists data across restarts
- Connection via `DATABASE_URL` env var
- Pool with `pool_pre_ping=True` for stale connection recovery

### Redis 7
- No persistence — cache only
- Used for GTFS-RT vehicle position cache (`gtfs:vehicles` key, 30s TTL)

## Webhooks / Background Jobs

- None currently. GTFS static ingest is a manual one-shot script.
