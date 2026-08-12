"""
SP survey API — /api/survey/*.

Full session lifecycle (start -> next -> choice -> complete), sequence/
ownership validation on choice recording, the admin-guarded CSV export,
and the opt-in (default-off) account attachment.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from datetime import datetime, timezone  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth import get_current_user_optional  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.ingest_sp import ingest  # noqa: E402
from app.models.sp import SPAlternative, SPChoiceTask, SPRespondent, SPResponse, SPSurvey  # noqa: E402
from app.models.user import User  # noqa: E402

SAMPLE_CSV = "docs/sample_survey.csv"


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine, tables=[
        User.__table__, SPSurvey.__table__, SPChoiceTask.__table__,
        SPAlternative.__table__, SPRespondent.__table__, SPResponse.__table__,
    ])
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    seed = TestSessionLocal()
    survey = ingest(seed, SAMPLE_CSV, "Test Survey", "desc", tasks_per_respondent=4, force=False)
    survey_id = survey.id
    seed.add(User(id="u-1", email="rider@example.com", display_name="Rider"))
    seed.commit()
    seed.close()

    monkeypatch.setenv("SP_ADMIN_KEY", "test-admin-key")

    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}), patch("app.main._wait_for_db", return_value=None):
        from app.main import app

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user_optional] = lambda: None

        with TestClient(app) as c:
            c.survey_id = survey_id
            c.session_local = TestSessionLocal
            yield c

        app.dependency_overrides.clear()


def test_start_session_returns_respondent_and_task_count(client):
    resp = client.post(f"/api/survey/{client.survey_id}/session", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["survey_id"] == client.survey_id
    assert body["block_id"] in ("A", "B")
    # Each block only has 2 tasks even though tasks_per_respondent=4.
    assert body["total_tasks"] == 2


def test_start_session_unknown_survey_404(client):
    resp = client.post("/api/survey/999999/session", json={})
    assert resp.status_code == 404


def test_full_session_walkthrough(client):
    start = client.post(f"/api/survey/{client.survey_id}/session", json={}).json()
    respondent_id = start["respondent_id"]
    total = start["total_tasks"]

    seen_task_numbers = []
    for _ in range(total):
        nxt = client.get(f"/api/survey/session/{respondent_id}/next").json()
        assert nxt["completed"] is False
        assert nxt["task"] is not None
        seen_task_numbers.append(nxt["task_number"])
        alt_id = nxt["task"]["alternatives"][0]["id"]
        choice = client.post(
            f"/api/survey/session/{respondent_id}/choice",
            json={
                "task_id": nxt["task"]["id"],
                "chosen_alternative_id": alt_id,
                "shown_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert choice.status_code == 204

    assert seen_task_numbers == list(range(1, total + 1))

    after_last = client.get(f"/api/survey/session/{respondent_id}/next").json()
    assert after_last["completed"] is True
    assert after_last["task"] is None

    complete = client.post(f"/api/survey/session/{respondent_id}/complete")
    assert complete.status_code == 200
    assert complete.json()["respondent_id"] == respondent_id

    # Idempotent — calling again doesn't error.
    complete2 = client.post(f"/api/survey/session/{respondent_id}/complete")
    assert complete2.status_code == 200
    assert complete2.json()["completed_at"] == complete.json()["completed_at"]


def test_choice_rejects_task_outside_respondents_sequence(client):
    start = client.post(f"/api/survey/{client.survey_id}/session", json={}).json()
    respondent_id = start["respondent_id"]

    # Find a task_id definitely not in this respondent's block.
    db = client.session_local()
    other_block = "B" if start["block_id"] == "A" else "A"
    foreign_task = db.query(SPChoiceTask).filter_by(survey_id=client.survey_id, block_id=other_block).first()
    foreign_alt = foreign_task.alternatives[0]
    db.close()

    resp = client.post(
        f"/api/survey/session/{respondent_id}/choice",
        json={
            "task_id": foreign_task.id,
            "chosen_alternative_id": foreign_alt.id,
            "shown_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert resp.status_code == 400


def test_choice_rejects_double_answer(client):
    start = client.post(f"/api/survey/{client.survey_id}/session", json={}).json()
    respondent_id = start["respondent_id"]
    nxt = client.get(f"/api/survey/session/{respondent_id}/next").json()
    task_id = nxt["task"]["id"]
    alt_id = nxt["task"]["alternatives"][0]["id"]
    body = {"task_id": task_id, "chosen_alternative_id": alt_id, "shown_at": datetime.now(timezone.utc).isoformat()}

    assert client.post(f"/api/survey/session/{respondent_id}/choice", json=body).status_code == 204
    resp2 = client.post(f"/api/survey/session/{respondent_id}/choice", json=body)
    assert resp2.status_code == 409


def test_choice_rejects_alternative_from_a_different_task(client):
    start = client.post(f"/api/survey/{client.survey_id}/session", json={}).json()
    respondent_id = start["respondent_id"]
    nxt = client.get(f"/api/survey/session/{respondent_id}/next").json()
    task_id = nxt["task"]["id"]

    db = client.session_local()
    other_task = db.query(SPChoiceTask).filter(SPChoiceTask.id != task_id).first()
    mismatched_alt_id = other_task.alternatives[0].id
    db.close()

    resp = client.post(
        f"/api/survey/session/{respondent_id}/choice",
        json={
            "task_id": task_id, "chosen_alternative_id": mismatched_alt_id,
            "shown_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert resp.status_code == 400


def test_next_unknown_respondent_404(client):
    resp = client.get("/api/survey/session/does-not-exist/next")
    assert resp.status_code == 404


def test_session_defaults_anonymous_even_when_signed_in(client):
    from app.main import app
    app.dependency_overrides[get_current_user_optional] = lambda: User(id="u-1", email="rider@example.com")
    try:
        resp = client.post(f"/api/survey/{client.survey_id}/session", json={})
        respondent_id = resp.json()["respondent_id"]
        db = client.session_local()
        respondent = db.get(SPRespondent, respondent_id)
        assert respondent.user_id is None  # attach_account not passed -> stays anonymous
        db.close()
    finally:
        app.dependency_overrides[get_current_user_optional] = lambda: None


def test_session_attaches_account_on_explicit_opt_in(client):
    from app.main import app
    app.dependency_overrides[get_current_user_optional] = lambda: User(id="u-1", email="rider@example.com")
    try:
        resp = client.post(f"/api/survey/{client.survey_id}/session", json={"attach_account": True})
        respondent_id = resp.json()["respondent_id"]
        db = client.session_local()
        respondent = db.get(SPRespondent, respondent_id)
        assert respondent.user_id == "u-1"
        db.close()
    finally:
        app.dependency_overrides[get_current_user_optional] = lambda: None


def test_export_requires_admin_key(client):
    resp = client.get(f"/api/survey/{client.survey_id}/export")
    assert resp.status_code == 401


def test_export_rejects_wrong_admin_key(client):
    resp = client.get(f"/api/survey/{client.survey_id}/export", headers={"X-Admin-Key": "wrong"})
    assert resp.status_code == 401


def test_export_returns_long_format_csv_with_chosen_flag(client):
    start = client.post(f"/api/survey/{client.survey_id}/session", json={}).json()
    respondent_id = start["respondent_id"]
    nxt = client.get(f"/api/survey/session/{respondent_id}/next").json()
    task = nxt["task"]
    chosen_alt_id = task["alternatives"][0]["id"]
    client.post(
        f"/api/survey/session/{respondent_id}/choice",
        json={
            "task_id": task["id"], "chosen_alternative_id": chosen_alt_id,
            "shown_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    resp = client.get(f"/api/survey/{client.survey_id}/export", headers={"X-Admin-Key": "test-admin-key"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().splitlines()
    header = lines[0].split(",")
    assert header[:5] == ["respondent_id", "block_id", "task_code", "alt_code", "chosen"]
    # One data row per alternative in the answered task.
    data_rows = lines[1:]
    assert len(data_rows) == len(task["alternatives"])
    chosen_flags = [row.split(",")[4] for row in data_rows]
    assert chosen_flags.count("1") == 1
    assert chosen_flags.count("0") == len(task["alternatives"]) - 1
