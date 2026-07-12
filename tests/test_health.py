"""
Minimal CI smoke test — verifies the app boots and /health returns 200.

Uses FastAPI's TestClient (which wraps httpx) so no running server is needed.
The lifespan DB retry is bypassed here: DATABASE_URL is unset so the engine
is never created; we mock _wait_for_db to a no-op.
"""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health():
    # db.py reads DATABASE_URL at import time; set a dummy value so the engine
    # can be constructed without connecting (SQLAlchemy is lazy on connect).
    # _wait_for_db is patched so no real DB connection is ever attempted.
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}):
        with patch("app.main._wait_for_db", return_value=None):
            from app.main import app

            with TestClient(app) as client:
                resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
