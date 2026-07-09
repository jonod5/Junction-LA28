# Architecture

_Last mapped: 2026-07-09_

## Pattern

**Layered REST API** — synchronous FastAPI backend with PostgreSQL for persistence and Redis for caching. No frontend in this repo; this is a data/API layer intended to power a trip-planning UI.

```
Client
  └── FastAPI (Uvicorn)
        ├── Routers (HTTP handlers)
        │     ├── /api/places      → Google Places proxy
        │     └── /api/vehicles    → GTFS-RT vehicle positions (Redis cache-first)
        ├── Ingest (one-shot scripts)
        │     ├── gtfs_static.py   → Bulk-load GTFS schedule data into Postgres
        │     └── gtfs_rt.py       → Fetch + cache LA Metro live vehicle positions
        ├── Models (ORM)
        │     ├── venue.py         → Venue + 5 child tables (parking, curb, transit, congestion, sources)
        │     └── gtfs.py          → GTFS mirror tables (stop, route, trip, stop_time)
        └── db.py                  → Engine, session factory, get_db() dependency
```

## Entry Points

- **`app/main.py`** — FastAPI app, lifespan hook (DB retry with exponential backoff), router registration, `/health` endpoint
- **`app/ingest/gtfs_static.py`** — run as `python -m app.ingest.gtfs_static` to reload GTFS schedule
- **`alembic/`** — DB migrations; run `alembic upgrade head` manually

## Data Flow

### Vehicle Positions (real-time)
```
GET /api/vehicles
  → Check Redis cache (gtfs:vehicles, 30s TTL)
  → Cache hit: return immediately
  → Cache miss: fetch LA Metro API (bus + rail), merge, write cache, return
```

### Places Search
```
GET /api/places?query=...
  → Server-side httpx call to Google Places Text Search
  → Return only {name, address} (strip billing-sensitive fields)
  → (TODO: Redis cache per query string)
```

### GTFS Static Ingest (manual)
```
python -m app.ingest.gtfs_static
  → Download rail + bus GTFS zips from GitLab (in-memory, no disk write)
  → Truncate all 4 GTFS mirror tables in one transaction
  → Bulk-insert stops (deduped by stop_id), routes, trips
  → Stream stop_times in 5000-row batches (bus feed = 3M+ rows)
  → Reset Postgres autoincrement sequence
```

## Key Design Decisions

- **Synchronous handlers** — app is synchronous (psycopg2, sync httpx). Async migration possible if needed.
- **GTFS mirror tables** — GTFS data is copied into Postgres rather than queried from flat files, enabling SQL joins against venue data.
- **DB startup retry** — `_wait_for_db` uses exponential backoff (up to ~2 min) to handle Docker race between backend and Postgres containers. Alembic is NOT auto-run to avoid running on every replica.
- **Google Maps key server-side only** — clients never see the API key; proxy strips internal Place fields before responding.
- **Redis cache-or-fetch** — `/api/vehicles` serves from cache on cache hit; fetches live on miss. Avoids stale fallback problem.
