# Structure

_Last mapped: 2026-07-09_

## Directory Layout

```
la28-trip-planner/
├── app/                        # Application source
│   ├── main.py                 # FastAPI app, lifespan, router registration, /health
│   ├── db.py                   # SQLAlchemy engine, SessionLocal, Base, get_db()
│   ├── models/
│   │   ├── venue.py            # Venue + 5 child tables ORM models
│   │   └── gtfs.py             # GTFS mirror tables ORM models
│   ├── routers/
│   │   ├── places.py           # GET /api/places (Google Places proxy)
│   │   └── vehicles.py         # GET /api/vehicles (GTFS-RT cache-first)
│   └── ingest/
│       ├── gtfs_static.py      # One-shot GTFS schedule bulk-load script
│       └── gtfs_rt.py          # GTFS-RT fetch + Redis cache logic
├── alembic/
│   ├── env.py                  # Alembic env config
│   ├── script.py.mako          # Migration template
│   └── versions/
│       └── 0001_initial_schema.py  # All tables: venue schema + GTFS mirrors
├── tests/
│   └── test_health.py          # Smoke test: app boots, /health returns 200
├── .planning/                  # GSD project planning docs (this folder)
├── Dockerfile                  # Backend image
├── docker-compose.yml          # 3-service stack: db, redis, backend
├── alembic.ini                 # Alembic config
├── requirements.txt            # Python dependencies
└── .env.example                # Environment variable template
```

## Key File Locations

| What | Where |
|------|-------|
| FastAPI app instance | `app/main.py` |
| DB connection setup | `app/db.py` |
| Venue data models | `app/models/venue.py` |
| GTFS schedule models | `app/models/gtfs.py` |
| Places API proxy | `app/routers/places.py` |
| Vehicle positions API | `app/routers/vehicles.py` |
| GTFS schedule ingest | `app/ingest/gtfs_static.py` |
| GTFS-RT live fetch | `app/ingest/gtfs_rt.py` |
| Initial DB migration | `alembic/versions/0001_initial_schema.py` |
| Health smoke test | `tests/test_health.py` |
| Docker services | `docker-compose.yml` |
| Env var template | `.env.example` |

## Naming Conventions

- Files: `snake_case.py`
- Router files named after the resource they serve (`places.py`, `vehicles.py`)
- Ingest files named after the data source format (`gtfs_static.py`, `gtfs_rt.py`)
- Migration files: `{sequence}_{description}.py` (e.g. `0001_initial_schema.py`)
- ORM models: `PascalCase` (e.g. `GtfsStop`, `ParkingOption`)
- Table names: `snake_case` matching resource (e.g. `gtfs_stop_time`, `parking_option`)
