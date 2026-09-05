"""Alembic environment. DDL owner as of ADR-004 (was Prisma/Node under ADR-003).

`target_metadata` stays None on purpose: `models.py` is mapping-only and carries
Python-side defaults rather than server defaults, so autogenerate would propose
dropping real DDL. Revisions are hand-written and locked by the structural
parity test (tests/test_schema_ddl.py) against docs/qa/adr-004-schema-baseline.json.
"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from jplearn_api.db import async_database_url

config = context.config

target_metadata = None


def _raw_url() -> str:
    url = config.get_main_option("sqlalchemy.url", None) or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required to run migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_raw_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = async_database_url(_raw_url())
    engine = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
