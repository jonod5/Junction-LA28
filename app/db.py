import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# DATABASE_URL must be set in the environment (via .env / docker-compose env_file).
# Example: postgresql+psycopg2://la28:changeme@db:5432/la28db
_raw_url = os.environ["DATABASE_URL"]
# Railway injects postgresql:// but psycopg2 needs postgresql+psycopg2://
DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)

# pool_pre_ping=True transparently reconnects stale connections; important
# because the backend container can restart while Postgres is still healthy.
_engine_kwargs: dict = {"pool_pre_ping": True}

# Pool sizing — SQLite (the test suite's DATABASE_URL) doesn't accept these
# kwargs at all, so they're Postgres-only. A load test found the un-tuned
# SQLAlchemy defaults (pool_size=5, max_overflow=10 → 15 total) exhausted
# under concurrent load well before 200 simultaneous requests, cascading
# into PoolTimeout/ReadTimeout errors across every DB-touching endpoint.
#
# Tune via env vars to fit your actual Postgres plan's max_connections,
# leaving headroom for other consumers (migrations, psql, etc.):
#   pool_size + max_overflow, PER WORKER PROCESS, must stay comfortably
#   under that ceiling. Running N Uvicorn workers (see Dockerfile's
#   WEB_CONCURRENCY) multiplies this by N, since each worker process gets
#   its own independent engine/pool — 2 workers x (10+20) = 60 connections.
if DATABASE_URL.startswith("postgresql"):
    _engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", "10"))
    _engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", "20"))
    _engine_kwargs["pool_timeout"] = int(os.environ.get("DB_POOL_TIMEOUT", "30"))

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a session, always closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
