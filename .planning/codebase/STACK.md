# Stack

_Last mapped: 2026-07-09_

## Language & Runtime

- **Python 3.12+** (inferred from `Mapped[str | None]` union syntax and modern SQLAlchemy usage)
- No frontend runtime — API-only backend

## Web Framework

- **FastAPI** — async-compatible, router-based; currently using sync handlers
- **Uvicorn** (standard extras) — ASGI server with `--reload` in dev

## Database

- **PostgreSQL 16** (Docker image)
- **SQLAlchemy 2.0** (ORM + Core) — `DeclarativeBase`, `Mapped`/`mapped_column` typed style
- **Alembic** — migration management; manual migrations (not auto-run on startup)
- **psycopg2-binary** — sync driver (no asyncpg; app is synchronous)

## Cache

- **Redis 7** (Docker image)
- **redis-py** — used for GTFS-RT vehicle position cache (30s TTL)

## HTTP Client

- **httpx** — sync client used for Google Places proxy and GTFS-RT fetches

## Containerisation

- **Docker + Docker Compose** — 3-service stack: `db`, `redis`, `backend`
- Backend hot-reloads via `./app:/app/app` volume mount

## Dev / CI Tools

- **ruff** — linter/formatter
- **pytest** + **pytest-asyncio** — test runner

## Configuration

All secrets via environment variables (`.env` file, injected via `env_file` in compose):
- `DATABASE_URL` — postgres connection string (required, no default)
- `REDIS_URL` — defaults to `redis://localhost:6379/0`
- `GOOGLE_MAPS_API_KEY` — required for `/api/places`
- `GTFS_STATIC_URLS` / `GTFS_STATIC_URL` — comma-separated GTFS zip URLs
- `GTFS_RT_VEHICLES_URLS` — comma-separated LA Metro vehicle position endpoints
- `GTFS_RT_API_KEY` — optional bearer token for GTFS-RT auth
- `POSTGRES_USER`, `POSTGRES_DB` — used by DB healthcheck in compose
