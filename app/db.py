import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# DATABASE_URL must be set in the environment (via .env / docker-compose env_file).
# Example: postgresql+psycopg2://la28:changeme@db:5432/la28db
DATABASE_URL = os.environ["DATABASE_URL"]

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
