"""Supabase JWT verification — app/auth.py."""

import os

# app.db reads DATABASE_URL at import time.
os.environ.setdefault("DATABASE_URL", "sqlite://")

import time  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import auth  # noqa: E402
from app.db import Base  # noqa: E402
from app.models.user import User  # noqa: E402

HS_SECRET = "test-secret-at-least-32-bytes-long-for-hs256"
SUB = "11111111-1111-1111-1111-111111111111"
EMAIL = "rider@example.com"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[User.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _request(token: str | None) -> SimpleNamespace:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return SimpleNamespace(headers=headers)


def _hs256_token(sub=SUB, email=EMAIL, secret=HS_SECRET, aud="authenticated", exp_delta=3600, **extra):
    payload = {"sub": sub, "email": email, "aud": aud, "exp": int(time.time()) + exp_delta, **extra}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_missing_authorization_header_raises_401(db_session):
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request(None), db_session)
    assert exc.value.status_code == 401


def test_non_bearer_scheme_raises_401(db_session):
    req = SimpleNamespace(headers={"Authorization": "Basic abc123"})
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(req, db_session)
    assert exc.value.status_code == 401


def test_no_config_raises_401(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request("whatever"), db_session)
    assert exc.value.status_code == 401
    assert "not configured" in exc.value.detail


def test_hs256_valid_token_creates_user(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    user = auth.get_current_user(_request(_hs256_token()), db_session)
    assert user.id == SUB
    assert user.email == EMAIL
    assert db_session.get(User, SUB) is not None


def test_hs256_reuses_existing_user_row(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token()
    first = auth.get_current_user(_request(token), db_session)
    second = auth.get_current_user(_request(token), db_session)
    assert first.id == second.id
    assert db_session.query(User).count() == 1


def test_hs256_updates_email_on_change(db_session, monkeypatch):
    db_session.add(User(id=SUB, email="old@example.com"))
    db_session.commit()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    user = auth.get_current_user(_request(_hs256_token(email="new@example.com")), db_session)
    assert user.email == "new@example.com"


def test_hs256_creates_user_with_avatar_url(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token(user_metadata={"full_name": "Rider One", "avatar_url": "https://example.com/a.jpg"})
    user = auth.get_current_user(_request(token), db_session)
    assert user.display_name == "Rider One"
    assert user.avatar_url == "https://example.com/a.jpg"


def test_hs256_updates_avatar_url_on_change(db_session, monkeypatch):
    db_session.add(User(id=SUB, email=EMAIL, avatar_url="https://example.com/old.jpg"))
    db_session.commit()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token(user_metadata={"avatar_url": "https://example.com/new.jpg"})
    user = auth.get_current_user(_request(token), db_session)
    assert user.avatar_url == "https://example.com/new.jpg"


def test_hs256_wrong_secret_raises_401(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token(secret="wrong-secret")
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request(token), db_session)
    assert exc.value.status_code == 401


def test_hs256_expired_token_raises_401(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token(exp_delta=-10)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request(token), db_session)
    assert exc.value.status_code == 401


def test_token_missing_claims_raises_401(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    payload = {"aud": "authenticated", "exp": int(time.time()) + 3600}  # no sub/email
    token = jwt.encode(payload, HS_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request(token), db_session)
    assert exc.value.status_code == 401


def test_oversized_sub_claim_raises_401_not_500(db_session, monkeypatch):
    # A signature-valid token whose `sub` doesn't fit users.id (String(36))
    # used to reach db.get(User, uid) and blow up as an unhandled
    # psycopg2.errors.StringDataRightTruncation (500) — must 401 instead.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token(sub=f"not-a-uuid-{SUB}")
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request(token), db_session)
    assert exc.value.status_code == 401


def test_non_uuid_sub_claim_raises_401(db_session, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    token = _hs256_token(sub="short-but-not-a-uuid")
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_request(token), db_session)
    assert exc.value.status_code == 401


def test_jwks_valid_token_creates_user(db_session, monkeypatch):
    # Real RSA keypair signed locally — monkeypatches the JWKS *lookup* only,
    # so this exercises real jwt.decode() verification without needing a
    # live Supabase project.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {"sub": SUB, "email": EMAIL, "aud": "authenticated", "exp": int(time.time()) + 3600},
        private_key,
        algorithm="RS256",
    )
    fake_signing_key = SimpleNamespace(key=private_key.public_key())

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, tok):
            return fake_signing_key

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    monkeypatch.setattr(auth, "_jwks_client_for", lambda url: FakeJWKClient())

    user = auth.get_current_user(_request(token), db_session)
    assert user.id == SUB
    assert user.email == EMAIL


def test_jwks_falls_back_to_hs256_when_jwks_lookup_fails(db_session, monkeypatch):
    # JWKS configured but the key lookup fails (e.g. project has no matching
    # key yet) — must fall through to the HS256 secret, not just 401.
    class FailingJWKClient:
        def get_signing_key_from_jwt(self, tok):
            raise jwt.PyJWKClientError("no matching key")

    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    monkeypatch.setattr(auth, "_jwks_client_for", lambda url: FailingJWKClient())

    user = auth.get_current_user(_request(_hs256_token()), db_session)
    assert user.id == SUB
