# Testing

_Last mapped: 2026-07-09_

## Test Runner

- **pytest** + **pytest-asyncio** (installed via `requirements.txt`)
- Run: `pytest` from repo root

## Current Coverage

| File | What it tests | Notes |
|------|--------------|-------|
| `tests/test_health.py` | App boots, `/health` returns `{"status": "ok"}` | Only test currently present |

## Testing Approach

### Health Smoke Test (`tests/test_health.py`)
- Uses `FastAPI.TestClient` (wraps httpx, no running server needed)
- Patches `app.main._wait_for_db` to a no-op so no real Postgres required
- Import of `app.main.app` is done inside the patch context so the lifespan runs with the mocked DB wait

### What's Not Tested Yet
- `/api/places` endpoint (requires mocking httpx + Google Maps API)
- `/api/vehicles` endpoint (requires mocking Redis + LA Metro API)
- GTFS static ingest (`app/ingest/gtfs_static.py`)
- GTFS-RT fetch logic (`app/ingest/gtfs_rt.py`)
- ORM models / database layer
- Venue CRUD operations (no CRUD endpoints exist yet)

## Running Tests

```bash
# From repo root (no Docker needed for current test suite)
pytest

# With output
pytest -v

# Inside Docker (if you need it)
docker compose run --rm backend pytest
```

## Notes

- `pytest-asyncio` is installed but not yet used — the app is synchronous; async tests would be needed if async endpoints are added
- No fixtures file yet (`conftest.py` does not exist)
- No coverage reporting configured
