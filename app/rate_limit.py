"""
Redis-backed rate limiting.

Two layers:
  - rate_limit(scope, max_requests, window_s): a FastAPI dependency factory
    for a STRICT per-endpoint cap, applied to the two routes that proxy to
    the real (paid, quota-limited) Google Maps API — /api/directions and
    /api/routes/optimize. Without this, any client could drive up Google
    billing directly through our own proxy; the backend-proxy pattern hides
    the API key but does nothing on its own to cap request volume.
  - GlobalRateLimitMiddleware: a looser default across every other route —
    generic abuse/scraping protection, not cost protection.

Fixed-window counter (INCR + EXPIRE-on-first-hit), not a sliding window or
token bucket — imprecise right at window boundaries (a client could in
theory get ~2x the nominal rate straddling a window edge), but simple,
correct enough for abuse protection, and needs nothing beyond Redis
(already a hard dependency everywhere else in this codebase — no new
package like slowapi, even though app/routers/places.py's docstring
name-drops it as a placeholder TODO).

Fails OPEN on Redis errors: a rate limiter is a defensive nice-to-have, not
a correctness-critical path — if Redis is briefly unreachable, requests
should still go through rather than the whole app 500ing or 429ing on
every request.
"""

import logging
import os

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.cache import get_redis

log = logging.getLogger(__name__)


def _client_key(request: Request) -> str:
    # request.client.host reflects the real client IP via X-Forwarded-For
    # once behind a proxy (Railway) — uvicorn's ProxyHeadersMiddleware
    # (already in the stack) rewrites it from the forwarded header.
    return request.client.host if request.client else "unknown"


def _check_and_increment(key: str, max_requests: int, window_s: int) -> bool:
    """Returns True if the request is allowed. Fails open (allows the
    request) if Redis itself is unreachable."""
    try:
        r = get_redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, window_s)
        return count <= max_requests
    except Exception:  # noqa: BLE001 — Redis being down must never break the app
        log.warning("Rate limiter could not reach Redis — failing open for %s", key)
        return True


def rate_limit(scope: str, max_requests: int, window_s: int):
    """FastAPI dependency factory: Depends(rate_limit("directions", 20, 60))."""

    def _dependency(request: Request) -> None:
        key = f"ratelimit:{scope}:{_client_key(request)}"
        if not _check_and_increment(key, max_requests, window_s):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded — max {max_requests} requests per {window_s}s",
            )

    return _dependency


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Looser default cap across every route — generic flooding/scraping
    protection, layered underneath the stricter per-endpoint limits above."""

    def __init__(self, app, max_requests: int = 300, window_s: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_s = window_s

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        key = f"ratelimit:global:{_client_key(request)}"
        if not _check_and_increment(key, self.max_requests, self.window_s):
            return JSONResponse(
                {"detail": f"Rate limit exceeded — max {self.max_requests} requests per {self.window_s}s"},
                status_code=429,
            )
        return await call_next(request)


# Overridable via env for load testing / tuning without a code change.
DIRECTIONS_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_DIRECTIONS_PER_MIN", "20"))
GLOBAL_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_GLOBAL_PER_MIN", "300"))
