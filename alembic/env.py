"""
Alembic migration environment.

Key choices:
- DATABASE_URL comes from os.environ, not alembic.ini, so credentials never
  appear in the committed ini file.
- target_metadata is set to Base.metadata so `alembic revision --autogenerate`
  can diff the ORM models against the live DB schema.
- We import all model modules explicitly so their tables are registered in
  Base.metadata before autogenerate runs.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure the project root is on sys.path so `app.*` imports resolve when
# Alembic is invoked from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import every model module so their Table objects appear in Base.metadata.
# Add new model files here as the schema grows.
from app.db import Base  # noqa: E402
import app.models.venue  # noqa: F401, E402
import app.models.gtfs   # noqa: F401, E402
import app.models.user   # noqa: F401, E402

target_metadata = Base.metadata

# Override the sqlalchemy.url from alembic.ini with the env var so no
# credentials are ever stored in the ini file.
DATABASE_URL = os.environ["DATABASE_URL"]
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool is correct for migration scripts
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
