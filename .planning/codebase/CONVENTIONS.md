# Conventions

_Last mapped: 2026-07-09_

## Code Style

- **Linter/formatter:** `ruff` (configured in requirements.txt; no `pyproject.toml` or `ruff.toml` found — using defaults)
- **Imports:** stdlib → third-party → local, each group alphabetically sorted
- **Line length:** ruff default (88)

## SQLAlchemy Patterns

- **ORM style:** SQLAlchemy 2.0 typed — `Mapped[T]` + `mapped_column()` for all columns
- **Nullable columns:** `Mapped[str | None]` (not `Optional[str]`)
- **Relationships:** `Mapped[list["ChildModel"]]` with `cascade="all, delete-orphan"` on parent side
- **Bulk inserts:** SQLAlchemy Core `insert()` (not ORM) for high-volume data (GTFS stop_times = 3M+ rows)
- **Session management:** `get_db()` dependency yields and always closes in `finally`

## FastAPI Patterns

- **Routers:** Each resource gets its own file in `app/routers/`; `APIRouter()` instance registered in `main.py`
- **Dependencies:** DB session via `Depends(get_db)`
- **Query params:** Typed with `Query(...)` including `min_length`/`max_length` validation
- **Error responses:** `HTTPException` with explicit status codes (502 for upstream failures, 500 for missing config)

## Error Handling

- External API errors: caught as `httpx.HTTPError`, logged with `log.exception()`, re-raised as `HTTPException(502)`
- Missing env vars: `DATABASE_URL` raises `KeyError` at startup (intentional fail-fast); `GOOGLE_MAPS_API_KEY` returns HTTP 500

## Provenance / Audit Pattern

Every child table row in the venue schema carries:
- `source: str` (required, URL or document name)
- `date_collected: date | None`
- `verified_at: datetime | None`
- `verified_by: str | None`
- `data_gaps: str | None`

This is a domain convention from the LA28 Venue Data Collection sheet — every fact must be traceable to a source.

## Comments

- Docstrings on modules explain design choices and usage (e.g. why sync not async, why Core not ORM for bulk insert)
- Inline `# TODO:` comments mark unimplemented work (Redis caching for Places, rate limiting)
- `# noqa` comments used sparingly with explanation (e.g. `# noqa: S310` for trusted URL)
