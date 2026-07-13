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
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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
