"""
Supabase JWT verification — FastAPI dependency for auth-required routes.

Supabase owns identity (Google sign-in, session, token issuance); this
module only ever *verifies* a token it's handed, and never calls Supabase's
API or holds a service key. Two verification paths, tried in order, so this
works against either kind of Supabase project without a code change:

  1. JWKS (current Supabase default) — asymmetric RS256/ES256, keys fetched
     and cached from Supabase's public JWKS endpoint, rotate automatically.
  2. HS256 shared-secret fallback (older/self-managed projects) — only used
     if SUPABASE_JWT_SECRET is set.

If SUPABASE_URL isn't configured at all, every request is treated as
unauthenticated (401) rather than raising at import time — mirrors the
graceful-degradation pattern already used for SWIFTLY_API_KEY etc.

The local `users` mirror row is get-or-created right here, inline, on every
successful verification — there's no separate signup endpoint, since
Supabase already created the identity; the mirror just needs to exist
before an itinerary can FK to it.
"""

import logging
import os
import uuid

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User

log = logging.getLogger(__name__)

# Supabase always issues access tokens with this audience.
_AUDIENCE = "authenticated"

_jwks_client: PyJWKClient | None = None
_jwks_client_url: str | None = None


def _supabase_url() -> str | None:
    return os.environ.get("SUPABASE_URL")


def _jwt_secret() -> str | None:
    return os.environ.get("SUPABASE_JWT_SECRET")


def _jwks_client_for(url: str) -> PyJWKClient:
    """Cache the PyJWKClient (and its internal key cache) across requests."""
    global _jwks_client, _jwks_client_url
    if _jwks_client is None or _jwks_client_url != url:
        _jwks_client = PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json")
        _jwks_client_url = url
    return _jwks_client


def _decode(token: str) -> dict:
    """Verify signature + exp/aud, return the claims. Raises HTTPException(401) on any failure."""
    last_error: Exception | None = None

    url = _supabase_url()
    if url:
        try:
            client = _jwks_client_for(url)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"], audience=_AUDIENCE)
        except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
            last_error = exc

    secret = _jwt_secret()
    if secret:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"], audience=_AUDIENCE)
        except jwt.InvalidTokenError as exc:
            last_error = exc

    log.info("JWT verification failed: %s", last_error)
    raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency — verifies the bearer token and returns the local
    `users` row (created on first sight). 401 on missing/invalid/expired
    token or missing config.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if not _supabase_url() and not _jwt_secret():
        raise HTTPException(status_code=401, detail="Auth is not configured")

    claims = _decode(token)
    uid = claims.get("sub")
    email = claims.get("email")
    if not uid or not email:
        raise HTTPException(status_code=401, detail="Token missing required claims")
    # Supabase always issues `sub` as a UUID and `email` well under 320
    # chars — a signature-valid but malformed/corrupted token (or a client
    # bug) with an oversized/malshaped claim would otherwise reach
    # db.get(User, uid) and fail as an unhandled psycopg2 DataError (500)
    # instead of a clean 401.
    try:
        uuid.UUID(uid)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=401, detail="Token has an invalid subject claim") from None
    if len(email) > 320:
        raise HTTPException(status_code=401, detail="Token has an invalid email claim")

    user_metadata = claims.get("user_metadata") or {}
    avatar_url = user_metadata.get("avatar_url")

    user = db.get(User, uid)
    if user is None:
        display_name = user_metadata.get("full_name")
        user = User(id=uid, email=email, display_name=display_name, avatar_url=avatar_url)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.email != email or user.avatar_url != avatar_url:
        # Email and Google avatar can both change (re-confirmed via Supabase
        # or a new profile photo) — keep the mirror current on every request
        # rather than only at signup.
        user.email = email
        user.avatar_url = avatar_url
        db.commit()
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    """
    Same as get_current_user, but returns None instead of raising when
    there's no (or an invalid) bearer token — for endpoints where signing in
    is optional, e.g. an anonymous-by-default SP survey session that a
    signed-in user may opt into attaching their account to.
    """
    if not request.headers.get("Authorization", "").startswith("Bearer "):
        return None
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None
