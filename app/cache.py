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


def get_redis() -> redis_lib.Redis:
    """Return a Redis client from REDIS_URL (default localhost)."""
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis_lib.from_url(url, decode_responses=True)
