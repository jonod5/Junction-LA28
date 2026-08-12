"""
SP survey CSV ingest — app/ingest_sp.py.

Covers CSV validation (required columns, numeric parsing, minimum
alternatives per task, consistent block_id) and idempotent re-ingest
against a real in-memory DB.
"""

import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base  # noqa: E402
from app.ingest_sp import ingest, parse_csv  # noqa: E402
from app.models.sp import SPAlternative, SPChoiceTask, SPResponse, SPSurvey  # noqa: E402
from app.models.user import User  # noqa: E402

SAMPLE_CSV = "docs/sample_survey.csv"


def _write_csv(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    f.write(content)
    f.close()
    return f.name


# ── parse_csv: pure validation ──────────────────────────────────────────────

def test_parses_sample_csv_clean():
    tasks, errors = parse_csv(SAMPLE_CSV)
    assert errors == []
    assert set(tasks.keys()) == {"T1", "T2", "T3", "T4"}
    assert len(tasks["T1"]) == 3
    assert tasks["T1"][0].extra == {"comfort_rating": 3}


def test_missing_required_column_reports_clearly():
    path = _write_csv("task_code,alt_code\nT1,A\n")
    _, errors = parse_csv(path)
    assert any("mode_label" in e for e in errors)


def test_task_with_one_alternative_is_an_error():
    path = _write_csv(
        "task_code,alt_code,mode_label,travel_time_min\nT1,A,Walk,10\n",
    )
    _, errors = parse_csv(path)
    assert any("T1" in e and "at least 2" in e for e in errors)


def test_non_numeric_attribute_reports_row_and_column():
    path = _write_csv(
        "task_code,alt_code,mode_label,travel_time_min\n"
        "T1,A,Walk,not-a-number\n"
        "T1,B,Bike,12\n",
    )
    _, errors = parse_csv(path)
    assert any("Row 2" in e and "travel_time_min" in e for e in errors)


def test_inconsistent_block_id_within_a_task_is_an_error():
    path = _write_csv(
        "task_code,block_id,alt_code,mode_label\n"
        "T1,A,A,Walk\n"
        "T1,B,B,Bike\n",
    )
    _, errors = parse_csv(path)
    assert any("inconsistent block_id" in e for e in errors)


def test_extra_columns_coerced_to_numbers_when_possible():
    path = _write_csv(
        "task_code,alt_code,mode_label,reliability,note\n"
        "T1,A,Walk,4.5,decent\n"
        "T1,B,Bike,3,ok\n",
    )
    tasks, errors = parse_csv(path)
    assert errors == []
    assert tasks["T1"][0].extra == {"reliability": 4.5, "note": "decent"}
    assert tasks["T1"][1].extra == {"reliability": 3, "note": "ok"}


def test_blank_optional_cells_are_none_not_zero():
    path = _write_csv(
        "task_code,alt_code,mode_label,travel_time_min,transfers\n"
        "T1,A,Walk,,\n"
        "T1,B,Bike,12,0\n",
    )
    tasks, errors = parse_csv(path)
    assert errors == []
    assert tasks["T1"][0].travel_time_min is None
    assert tasks["T1"][0].transfers is None
    assert tasks["T1"][1].transfers == 0


# ── ingest(): DB-backed, idempotency ────────────────────────────────────────

def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    # SQLite doesn't enforce FK constraints (including ON DELETE CASCADE) by
    # default, unlike Postgres — without this, the force-reingest cascade
    # test would pass or fail based on nothing but the test DB's default.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine, tables=[
        User.__table__, SPSurvey.__table__, SPChoiceTask.__table__,
        SPAlternative.__table__, SPResponse.__table__,
    ])
    # sp_respondent has an FK to users — include it via metadata for the FK
    # to resolve, even though these tests don't exercise respondents.
    from app.models.sp import SPRespondent
    Base.metadata.create_all(engine, tables=[SPRespondent.__table__])
    return sessionmaker(bind=engine)()


def test_ingest_creates_survey_tasks_and_alternatives():
    session = _session()
    survey = ingest(session, SAMPLE_CSV, "Test Survey", "desc", 4, force=False)
    assert survey.id is not None
    assert survey.tasks_per_respondent == 4
    assert session.query(SPChoiceTask).filter_by(survey_id=survey.id).count() == 4
    assert session.query(SPAlternative).join(SPChoiceTask).filter(SPChoiceTask.survey_id == survey.id).count() == 10


def test_reingest_by_same_name_replaces_not_duplicates():
    session = _session()
    survey1 = ingest(session, SAMPLE_CSV, "Test Survey", None, 4, force=False)
    survey2 = ingest(session, SAMPLE_CSV, "Test Survey", None, 4, force=False)
    assert survey1.id == survey2.id
    assert session.query(SPSurvey).count() == 1
    assert session.query(SPChoiceTask).filter_by(survey_id=survey1.id).count() == 4


def test_reingest_refuses_when_responses_exist_without_force():
    session = _session()
    survey = ingest(session, SAMPLE_CSV, "Test Survey", None, 4, force=False)
    task = session.query(SPChoiceTask).filter_by(survey_id=survey.id).first()
    alt = task.alternatives[0]
    from datetime import datetime, timezone

    from app.models.sp import SPRespondent
    respondent = SPRespondent(survey_id=survey.id)
    session.add(respondent)
    session.flush()
    session.add(SPResponse(
        respondent_id=respondent.id, task_id=task.id, chosen_alternative_id=alt.id,
        shown_at=datetime.now(timezone.utc),
    ))
    session.commit()

    try:
        ingest(session, SAMPLE_CSV, "Test Survey", None, 4, force=False)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "response" in str(exc).lower()


def test_reingest_with_force_proceeds_despite_responses():
    session = _session()
    survey = ingest(session, SAMPLE_CSV, "Test Survey", None, 4, force=False)
    task = session.query(SPChoiceTask).filter_by(survey_id=survey.id).first()
    alt = task.alternatives[0]
    from datetime import datetime, timezone

    from app.models.sp import SPRespondent
    respondent = SPRespondent(survey_id=survey.id)
    session.add(respondent)
    session.flush()
    session.add(SPResponse(
        respondent_id=respondent.id, task_id=task.id, chosen_alternative_id=alt.id,
        shown_at=datetime.now(timezone.utc),
    ))
    session.commit()

    survey2 = ingest(session, SAMPLE_CSV, "Test Survey", None, 4, force=True)
    assert survey2.id == survey.id
    # The old response was cascaded away along with the old task rows.
    assert session.query(SPResponse).count() == 0


def test_ingest_raises_on_invalid_csv_without_touching_db():
    session = _session()
    path = _write_csv("task_code,alt_code,mode_label\nT1,A,Walk\n")  # only 1 alt
    try:
        ingest(session, path, "Bad Survey", None, 4, force=False)
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert session.query(SPSurvey).count() == 0
