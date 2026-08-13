"""
Concurrency test for app.routers.survey.record_choice's "already answered"
race — two submits for the same respondent+task at once.

Needs genuine separate DB connections with real transaction isolation to
reproduce, same reasoning as tests/test_itineraries_concurrency.py — a temp
file-based SQLite DB and real threads, not the shared-connection fixture
test_survey_api.py uses.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import tempfile  # noqa: E402
import threading  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.models.sp import SPAlternative, SPChoiceTask, SPRespondent, SPResponse, SPSurvey  # noqa: E402
from app.routers.survey import ChoiceRequest, record_choice  # noqa: E402


def test_record_choice_survives_concurrent_double_submit():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine, tables=[
            SPSurvey.__table__, SPChoiceTask.__table__, SPAlternative.__table__,
            SPRespondent.__table__, SPResponse.__table__,
        ])
        Session = sessionmaker(bind=engine)

        with Session() as seed:
            survey = SPSurvey(name="Concurrency Test", tasks_per_respondent=1)
            seed.add(survey)
            seed.flush()
            task = SPChoiceTask(survey_id=survey.id, task_code="T1")
            seed.add(task)
            seed.flush()
            alt_a = SPAlternative(task_id=task.id, alt_code="A", mode_label="Walk")
            alt_b = SPAlternative(task_id=task.id, alt_code="B", mode_label="Transit")
            seed.add_all([alt_a, alt_b])
            respondent = SPRespondent(survey_id=survey.id)
            seed.add(respondent)
            seed.commit()
            respondent_id = respondent.id
            task_id = task.id
            alt_id = alt_a.id

        barrier = threading.Barrier(2)
        results: dict[str, object] = {}

        def worker(key: str) -> None:
            db = Session()
            try:
                barrier.wait(timeout=5)
                body = ChoiceRequest(
                    task_id=task_id, chosen_alternative_id=alt_id,
                    shown_at=datetime.now(timezone.utc),
                )
                record_choice(respondent_id, body, db)
                results[key] = "ok"
            except HTTPException as exc:
                results[key] = exc.status_code
            except BaseException as exc:  # noqa: BLE001
                results[key] = exc
            finally:
                db.close()

        threads = [threading.Thread(target=worker, args=(k,)) for k in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Exactly one side must have recorded the choice; the other must
        # get a clean 409, never a raw exception and never both succeeding.
        outcomes = sorted(results.values(), key=str)
        assert outcomes == [409, "ok"], f"unexpected outcomes: {results}"

        with Session() as check:
            count = (
                check.query(SPResponse)
                .filter_by(respondent_id=respondent_id, task_id=task_id)
                .count()
            )
        assert count == 1, "the race must not create a duplicate response row"
    finally:
        os.remove(path)
