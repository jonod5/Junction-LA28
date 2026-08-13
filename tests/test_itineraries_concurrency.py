"""
Concurrency test for app.routers.itineraries._resolve_tags's get-or-create
race — two requests creating the same brand-new tag at once.

This needs genuine separate DB connections with real transaction isolation
to reproduce (SELECT sees nothing on both sides, then one INSERT wins the
(user_id, name) unique constraint and the other must recover) — the shared
in-memory StaticPool connection used by test_itineraries.py's fixture
doesn't give that isolation, so this uses a temp file-based SQLite DB and
real threads instead.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import tempfile  # noqa: E402
import threading  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models.itinerary import ItineraryTag  # noqa: E402
from app.models.user import User  # noqa: E402
from app.routers.itineraries import _resolve_tags  # noqa: E402

USER_ID = "c0000000-0000-0000-0000-000000000003"


def test_resolve_tags_survives_concurrent_creation_race():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine, tables=[User.__table__, ItineraryTag.__table__])
        Session = sessionmaker(bind=engine)

        with Session() as seed:
            seed.add(User(id=USER_ID, email="c@example.com"))
            seed.commit()

        # Forces both threads to call _resolve_tags at (as close to)
        # the same instant as possible, so their existence-checks both
        # run before either side's insert commits.
        barrier = threading.Barrier(2)
        results: dict[str, int] = {}
        errors: dict[str, BaseException] = {}

        def worker(key: str) -> None:
            db = Session()
            try:
                user = db.get(User, USER_ID)
                barrier.wait(timeout=5)
                tags = _resolve_tags(["Family"], user, db)
                db.commit()
                results[key] = tags[0].id
            except BaseException as exc:  # noqa: BLE001 — a thread's exception must surface, not vanish
                errors[key] = exc
            finally:
                db.close()

        threads = [threading.Thread(target=worker, args=(k,)) for k in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"a concurrent request raised instead of recovering: {errors}"
        assert results["a"] == results["b"], "both requests must converge on the same tag row"

        with Session() as check:
            count = check.query(ItineraryTag).filter_by(user_id=USER_ID, name="Family").count()
        assert count == 1, "the race must not create a duplicate tag row"
    finally:
        os.remove(path)
