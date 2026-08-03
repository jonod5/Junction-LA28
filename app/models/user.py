"""
User — local mirror of a Supabase Auth identity.

Design choices:
- id is the Supabase auth.users UUID itself, not a separate local integer PK.
  Using the same id means Trip/Itinerary FKs can reference it directly with
  no lookup, and there's no drift between "our" user and Supabase's.
- id is a plain String(36), not Postgres's native UUID type — matches the
  existing Trip.user_id precedent (String(100), "reserved for future auth"),
  and Postgres's UUID type has a real dialect bug under SQLite (used by this
  test suite): result-row processing raises trying to coerce a UUID string
  through the wrong path. A plain string sidesteps it entirely and works
  identically on both dialects.
- Supabase owns identity (password, OAuth, session) — this table only mirrors
  the fields our app actually reads (email, display name) so itinerary
  queries never need to call out to Supabase per request.
- Row is get-or-created on first authenticated request (see app.auth), not
  via a dedicated signup endpoint — there's nothing else for a signup step
  to do, since Supabase already created the identity.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
