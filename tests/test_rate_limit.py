"""Redis-backed rate limiting — app/rate_limit.py."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import rate_limit as rl  # noqa: E402


class FakeRedis:
    """Minimal INCR/EXPIRE fake — matches the subset app.rate_limit uses."""

    def __init__(self):
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, ttl):
        self.ttls[key] = ttl


class RaisingRedis:
    def incr(self, key):
        raise ConnectionError("redis unreachable")


def _request(ip: str = "1.2.3.4") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip))


# ── _check_and_increment ─────────────────────────────────────────────────────

def test_allows_requests_under_the_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    for _ in range(5):
        assert rl._check_and_increment("k", max_requests=5, window_s=60) is True


def test_blocks_requests_over_the_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    for _ in range(5):
        rl._check_and_increment("k", max_requests=5, window_s=60)
    assert rl._check_and_increment("k", max_requests=5, window_s=60) is False


def test_sets_ttl_only_on_first_increment(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    rl._check_and_increment("k", max_requests=5, window_s=60)
    rl._check_and_increment("k", max_requests=5, window_s=60)
    assert fake.ttls == {"k": 60}  # expire() called exactly once, on count==1


def test_different_keys_have_independent_budgets(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    for _ in range(5):
        rl._check_and_increment("client-a", max_requests=5, window_s=60)
    assert rl._check_and_increment("client-a", max_requests=5, window_s=60) is False
    assert rl._check_and_increment("client-b", max_requests=5, window_s=60) is True


def test_fails_open_when_redis_unreachable(monkeypatch):
    monkeypatch.setattr(rl, "get_redis", lambda: RaisingRedis())
    assert rl._check_and_increment("k", max_requests=1, window_s=60) is True
    assert rl._check_and_increment("k", max_requests=1, window_s=60) is True


# ── rate_limit() dependency factory ─────────────────────────────────────────

def test_dependency_raises_429_over_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    dep = rl.rate_limit("scope-a", max_requests=2, window_s=60)
    dep(_request())
    dep(_request())
    with pytest.raises(HTTPException) as exc:
        dep(_request())
    assert exc.value.status_code == 429


def test_dependency_scopes_are_independent(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    dep_a = rl.rate_limit("scope-a", max_requests=1, window_s=60)
    dep_b = rl.rate_limit("scope-b", max_requests=1, window_s=60)
    dep_a(_request())
    dep_b(_request())  # must not be blocked by scope-a's budget
    with pytest.raises(HTTPException):
        dep_a(_request())


def test_dependency_keys_by_client_ip(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)
    dep = rl.rate_limit("scope-a", max_requests=1, window_s=60)
    dep(_request("1.1.1.1"))
    dep(_request("2.2.2.2"))  # different client, independent budget
    with pytest.raises(HTTPException):
        dep(_request("1.1.1.1"))


# ── GlobalRateLimitMiddleware ────────────────────────────────────────────────

@pytest.fixture
def app_client(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis", lambda: fake)

    app = FastAPI()
    app.add_middleware(rl.GlobalRateLimitMiddleware, max_requests=3, window_s=60)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/thing")
    def thing():
        return {"ok": True}

    return TestClient(app)


def test_middleware_allows_under_limit(app_client):
    for _ in range(3):
        assert app_client.get("/api/thing").status_code == 200


def test_middleware_blocks_over_limit(app_client):
    for _ in range(3):
        app_client.get("/api/thing")
    resp = app_client.get("/api/thing")
    assert resp.status_code == 429


def test_middleware_exempts_health(app_client):
    for _ in range(10):
        assert app_client.get("/health").status_code == 200
