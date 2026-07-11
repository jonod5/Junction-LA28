"""
Minimal CI smoke test — verifies the app boots and /health returns 200.

Uses FastAPI's TestClient (which wraps httpx) so no running server is needed.
The lifespan DB retry is bypassed here: DATABASE_URL is unset so the engine
is never created; we mock _wait_for_db to a no-op.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health():
    # Patch the DB wait so the test doesn't need a real Postgres instance.
    with patch("app.main._wait_for_db", return_value=None):
        # Import inside the patch so the patched version is active during
        # app construction (lifespan runs at TestClient context entry).
        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
