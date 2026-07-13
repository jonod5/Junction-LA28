"""
Application entry point.

Startup sequence:
  1. lifespan context manager retries the DB connection with exponential
     backoff (up to ~2 minutes total).  This handles the race between the
     backend container starting and Postgres finishing initialisation, even
     when the docker-compose healthcheck fires slightly early.
  2. Alembic is NOT run automatically on startup — run migrations manually
     or in a dedicated init container so they don't run on every replica.
"""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import engine
from app.routers import directions, places, trips, vehicles, venues

log = logging.getLogger(__name__)


def _wait_for_db(max_attempts: int = 10) -> None:
    """Retry the DB connection with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("Database connection established.")
            return
        except Exception as exc:  # noqa: BLE001
            wait = min(2**attempt, 60)
            log.warning(
                "DB not ready (attempt %d/%d): %s — retrying in %ds",
                attempt + 1,
                max_attempts,
                exc,
                wait,
            )
            time.sleep(wait)
    raise RuntimeError("Could not connect to the database after multiple retries.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _wait_for_db()
    yield
    # Nothing to tear down; SQLAlchemy connection pool closes automatically.


app = FastAPI(
    title="LA28 Trip Planner API",
    description="Multi-modal trip planning for LA28 Olympic venues",
    version="0.1.0",
    lifespan=lifespan,
)

_default_origins = [
    "http://localhost:8081",
    "http://localhost:19006",
    "http://localhost:3000",
]
_extra = os.environ.get("CORS_ORIGINS", "")
_allowed_origins = _default_origins + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehicles.router)
app.include_router(places.router)
app.include_router(trips.router)
app.include_router(directions.router)
app.include_router(venues.router)


@app.get("/health")
def health():
    """Lightweight liveness probe — does not touch the DB."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "LA28 Trip Planner API is running"}
