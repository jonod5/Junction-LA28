"""
Shared Redis accessor.

Every module that touches Redis (directions proxy, GTFS-RT, GBFS) used to
carry its own copy of this helper.  Centralising it here means one place to
change the connection URL, decode behaviour, or pooling strategy — and one
place for tests to monkeypatch.

decode_responses=True keeps the rest of the codebase working with str values
(we json.dumps/json.loads around it) rather than bytes.
"""

import os

import redis as redis_lib

# A single process-wide client, not a fresh one per get_redis() call — a
# redis.Redis instance already owns and manages its own internal connection
# pool, so constructing a brand-new one on every call (the previous
# behaviour here) discarded that pool and paid full connection setup cost
# every time. A load test showed this was the dominant latency cost on
# Redis-heavy request paths (route_engine.optimize() alone calls get_redis()
# 4-6+ times per request across its mode/micromobility lookups). Benign
# init race under concurrent first-calls (Python's GIL makes each
# assignment atomic; worst case a couple of short-lived extra clients get
# created and garbage collected before every caller converges on one) —
# same pattern already accepted for app.auth's _jwks_client cache.
_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    """Return the shared Redis client, built from REDIS_URL on first use."""
    global _client
    if _client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _client = redis_lib.from_url(url, decode_responses=True)
    return _client
