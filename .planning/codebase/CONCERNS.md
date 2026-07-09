# Concerns

_Last mapped: 2026-07-09_

## Known TODOs (in code)

| Location | TODO | Risk |
|----------|------|------|
| `app/routers/places.py:14` | Add Redis cache for Places API responses (per-query, short TTL) | API cost / rate limit exposure |
| `app/routers/places.py:15` | Add rate-limit middleware (e.g. slowapi) before public exposure | Abuse / quota exhaustion |

## Technical Debt

### No Read/Write API for Venue Data
- The venue schema (6 tables) is fully modelled in ORM and migrated, but there are **no CRUD endpoints** for it. Data can only be inserted directly into the DB. This is the most significant gap between the data model and a usable product.

### Synchronous App with Async Framework
- FastAPI is used synchronously (sync `def` handlers, psycopg2, sync httpx). This is fine for low concurrency but limits throughput. If the app handles concurrent users, switching to async handlers + asyncpg would be worthwhile.

### GTFS Static Ingest is Manual
- `python -m app.ingest.gtfs_static` must be run by hand whenever the feed updates. No scheduler, no cron, no webhook trigger. For a production system, this should be automated.

### Single Migration File
- All tables are in `0001_initial_schema.py`. As the schema grows, migrations should be separate files per change.

### No Authentication / Authorization
- No auth on any endpoint. `/api/places` and `/api/vehicles` are public. Venue write endpoints (when added) would need auth before any exposure.

### Missing `.env` Validation
- `DATABASE_URL` raises a `KeyError` at import time (fail-fast is good), but `GOOGLE_MAPS_API_KEY` is only checked at request time. Missing env vars should ideally be caught at startup.

## Risks

- **Google Maps API key exposure** — currently protected server-side; must stay that way. Any frontend code that calls Google directly would expose the key.
- **GTFS feed URL changes** — hardcoded default URLs in `gtfs_rt.py`; if LA Metro changes their API path, the fallback breaks silently until `GTFS_RT_VEHICLES_URLS` is overridden.
- **stop_times volume** — LA Metro bus `stop_times.txt` can be 3M+ rows. The current batched insert handles this, but the full ingest can take minutes and blocks the DB during truncate.
