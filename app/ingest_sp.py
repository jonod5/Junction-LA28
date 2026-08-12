"""
CSV ingest for the stated-preference (SP) survey pipeline.

    python -m app.ingest_sp <survey.csv> --name "LA28 SP v1" \
        [--description "..."] [--tasks-per-respondent 10] [--force]

CSV format is documented in docs/sp_survey_csv_format.md — one row per
alternative, columns: task_code, block_id (optional), alt_code, mode_label,
travel_time_min, cost_usd, walk_time_min, transfers, plus any extra
attribute columns (stored in each alternative's `extra` JSON).

Idempotent by survey name: re-running against the same --name replaces that
survey's tasks/alternatives entirely (delete + re-insert from the CSV) —
it does not duplicate or merge. If that survey already has recorded
responses, re-ingesting would orphan them (cascading deletes them along
with the tasks they reference), so this refuses to proceed unless --force
is passed.

All validation errors are collected and reported together before anything
touches the database — a bad CSV never partially ingests.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.sp import SPAlternative, SPChoiceTask, SPResponse, SPSurvey

REQUIRED_COLUMNS = {"task_code", "alt_code", "mode_label"}
NUMERIC_COLUMNS = {"travel_time_min", "cost_usd", "walk_time_min"}
INT_COLUMNS = {"transfers"}
KNOWN_COLUMNS = REQUIRED_COLUMNS | NUMERIC_COLUMNS | INT_COLUMNS | {"block_id"}


@dataclass
class ParsedAlternative:
    row_num: int
    alt_code: str
    mode_label: str
    block_id: str | None
    travel_time_min: float | None
    cost_usd: float | None
    walk_time_min: float | None
    transfers: int | None
    extra: dict = field(default_factory=dict)


def _coerce_extra(value: str) -> int | float | str:
    """Extra (unrecognized) columns: numeric-looking values become numbers, else stay strings."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_csv(path: str) -> tuple[dict[str, list[ParsedAlternative]], list[str]]:
    """
    Returns (tasks, errors). tasks maps task_code -> ordered list of
    ParsedAlternative (insertion order preserved). If errors is non-empty,
    tasks should not be trusted/used.
    """
    errors: list[str] = []
    tasks: dict[str, list[ParsedAlternative]] = {}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return {}, ["CSV has no header row"]
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            return {}, [f"Missing required column(s): {', '.join(sorted(missing))}"]
        extra_columns = [c for c in reader.fieldnames if c not in KNOWN_COLUMNS]

        for row_num, row in enumerate(reader, start=2):  # header is row 1
            task_code = (row.get("task_code") or "").strip()
            alt_code = (row.get("alt_code") or "").strip()
            mode_label = (row.get("mode_label") or "").strip()
            if not task_code:
                errors.append(f"Row {row_num}: task_code is required")
                continue
            if not alt_code:
                errors.append(f"Row {row_num}: alt_code is required")
                continue
            if not mode_label:
                errors.append(f"Row {row_num}: mode_label is required")
                continue

            block_id = (row.get("block_id") or "").strip() or None

            numeric_values: dict[str, float | None] = {}
            row_ok = True
            for col in NUMERIC_COLUMNS:
                raw = (row.get(col) or "").strip()
                if not raw:
                    numeric_values[col] = None
                    continue
                try:
                    numeric_values[col] = float(raw)
                except ValueError:
                    errors.append(f"Row {row_num}: column '{col}' is not numeric: {raw!r}")
                    row_ok = False

            transfers: int | None = None
            raw_transfers = (row.get("transfers") or "").strip()
            if raw_transfers:
                try:
                    transfers = int(raw_transfers)
                except ValueError:
                    errors.append(f"Row {row_num}: column 'transfers' is not an integer: {raw_transfers!r}")
                    row_ok = False

            if not row_ok:
                continue

            extra = {c: _coerce_extra(row[c]) for c in extra_columns if (row.get(c) or "").strip()}

            tasks.setdefault(task_code, []).append(ParsedAlternative(
                row_num=row_num,
                alt_code=alt_code,
                mode_label=mode_label,
                block_id=block_id,
                travel_time_min=numeric_values["travel_time_min"],
                cost_usd=numeric_values["cost_usd"],
                walk_time_min=numeric_values["walk_time_min"],
                transfers=transfers,
                extra=extra,
            ))

    for task_code, alts in tasks.items():
        if len(alts) < 2:
            errors.append(f"Task '{task_code}' has only {len(alts)} alternative(s) — needs at least 2")
        block_ids = {a.block_id for a in alts}
        if len(block_ids) > 1:
            errors.append(
                f"Task '{task_code}' has inconsistent block_id across its rows: {sorted(b or '(none)' for b in block_ids)}",
            )

    return tasks, errors


def ingest(
    session: Session,
    csv_path: str,
    name: str,
    description: str | None,
    tasks_per_respondent: int,
    force: bool,
) -> SPSurvey:
    tasks, errors = parse_csv(csv_path)
    if errors:
        raise ValueError("CSV validation failed:\n  " + "\n  ".join(errors))

    survey = session.query(SPSurvey).filter(SPSurvey.name == name).first()
    if survey:
        existing_task_ids = [t.id for t in session.query(SPChoiceTask).filter(SPChoiceTask.survey_id == survey.id)]
        response_count = 0
        if existing_task_ids:
            response_count = (
                session.query(SPResponse).filter(SPResponse.task_id.in_(existing_task_ids)).count()
            )
        if response_count and not force:
            raise ValueError(
                f"Survey '{name}' already has {response_count} recorded response(s). "
                "Re-ingesting would delete the tasks they reference (cascading away those "
                "responses). Pass --force to proceed anyway.",
            )
        for task in list(session.query(SPChoiceTask).filter(SPChoiceTask.survey_id == survey.id)):
            session.delete(task)
        session.flush()
        survey.description = description
        survey.tasks_per_respondent = tasks_per_respondent
    else:
        survey = SPSurvey(name=name, description=description, tasks_per_respondent=tasks_per_respondent)
        session.add(survey)
        session.flush()

    for task_code, alts in tasks.items():
        task = SPChoiceTask(survey_id=survey.id, task_code=task_code, block_id=alts[0].block_id)
        session.add(task)
        session.flush()
        for a in alts:
            session.add(SPAlternative(
                task_id=task.id,
                alt_code=a.alt_code,
                mode_label=a.mode_label,
                travel_time_min=a.travel_time_min,
                cost_usd=a.cost_usd,
                walk_time_min=a.walk_time_min,
                transfers=a.transfers,
                extra=a.extra,
            ))

    session.commit()
    return survey


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a stated-preference survey CSV.")
    parser.add_argument("csv_path")
    parser.add_argument("--name", required=True, help="Survey name — re-running with the same name replaces it")
    parser.add_argument("--description", default=None)
    parser.add_argument("--tasks-per-respondent", type=int, default=10)
    parser.add_argument(
        "--force", action="store_true",
        help="Allow replacing a survey that already has recorded responses (they will be deleted)",
    )
    args = parser.parse_args()

    import os

    from sqlalchemy import create_engine

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with Session(engine) as session:
        try:
            survey = ingest(
                session, args.csv_path, args.name, args.description, args.tasks_per_respondent, args.force,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        task_count = session.query(SPChoiceTask).filter(SPChoiceTask.survey_id == survey.id).count()
        alt_count = (
            session.query(SPAlternative)
            .join(SPChoiceTask)
            .filter(SPChoiceTask.survey_id == survey.id)
            .count()
        )
        print(f"Ingested survey '{survey.name}' (id={survey.id}): {task_count} tasks, {alt_count} alternatives.")


if __name__ == "__main__":
    main()
