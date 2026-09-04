"""ADR-004 DDL gate: Alembic must reproduce the schema Prisma owned.

The baseline JSON was captured from a Prisma-migrated database on 2026-09-04,
before `apps/api` was removed (docs/qa/adr-004-schema-baseline.json). If a future
revision changes the schema on purpose, regenerate the baseline in the same
commit — never loosen this test.

Also re-asserts FR-NEG-004 on the live schema, which is what
apps/api/test/schema.guard.spec.ts used to do from the Node side.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import asyncpg
import pytest

from jplearn_api.migrate import downgrade, stamp, upgrade
from jplearn_api.schema_snapshot import diff, snapshot_url
from pg_harness import (
    seed_database,
    start_docker_postgres,
    stop_docker_postgres,
)

BASELINE = Path(__file__).resolve().parents[3] / "docs" / "qa" / "adr-004-schema-baseline.json"

BANNED_COLUMNS = ("vocabulary_score", "grammar_lesson_id", "textbook_percent", "translation_vi")


@pytest.fixture(scope="module")
def alembic_database() -> str:
    project = "jplearn-ddl-gate"
    stop_docker_postgres(project)
    url = start_docker_postgres(project)
    try:
        yield url
    finally:
        stop_docker_postgres(project)


def test_alembic_schema_matches_prisma_baseline(alembic_database: str) -> None:
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    actual = asyncio.run(snapshot_url(alembic_database))
    problems = diff(expected, actual)
    assert not problems, "Alembic schema drifted from the Prisma baseline:\n" + "\n".join(problems)


def test_live_schema_has_no_textbook_columns(alembic_database: str) -> None:
    async def columns() -> list[str]:
        conn = await asyncpg.connect(alembic_database)
        try:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public'",
            )
            return [row["column_name"] for row in rows]
        finally:
            await conn.close()

    names = asyncio.run(columns())
    for banned in BANNED_COLUMNS:
        assert banned not in names, f"FR-NEG-004: banned column {banned} present in public schema"
    assert "minutes_comprehensible" in names
    assert "current_ci_level" in names


def test_downgrade_then_upgrade_returns_to_baseline(alembic_database: str) -> None:
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    downgrade("base", alembic_database)
    emptied = asyncio.run(snapshot_url(alembic_database))
    assert emptied["tables"] == {}, "downgrade left tables behind"

    upgrade(alembic_database)
    restored = asyncio.run(snapshot_url(alembic_database))
    assert not diff(expected, restored), "re-upgrade did not restore the baseline schema"


def test_stamp_adopts_a_database_built_before_alembic(alembic_database: str) -> None:
    """ADR-004 adoption path for databases Prisma built (dev, staging).

    Such a database already has the full schema but no `alembic_version`, so
    `upgrade` would try to CREATE TYPE on existing types. Dropping the bookkeeping
    table reproduces that state; `stamp` must adopt it and leave `upgrade` a no-op.
    """
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))

    async def drop_bookkeeping() -> None:
        conn = await asyncpg.connect(alembic_database)
        try:
            await conn.execute("DROP TABLE IF EXISTS alembic_version")
        finally:
            await conn.close()

    async def stamped_revision() -> str | None:
        conn = await asyncpg.connect(alembic_database)
        try:
            return await conn.fetchval("SELECT version_num FROM alembic_version")
        finally:
            await conn.close()

    asyncio.run(drop_bookkeeping())
    stamp("0001_prisma_baseline", alembic_database)
    assert asyncio.run(stamped_revision()) == "0001_prisma_baseline"

    upgrade(alembic_database)
    assert not diff(expected, asyncio.run(snapshot_url(alembic_database))), (
        "upgrade after stamp must not touch an adopted schema"
    )


def test_seed_is_idempotent_and_keeps_seed_items_draft(alembic_database: str) -> None:
    seed_database(alembic_database)
    seed_database(alembic_database)

    async def read() -> tuple[list, list, int, int]:
        conn = await asyncpg.connect(alembic_database)
        try:
            items = await conn.fetch(
                "SELECT id, status::text AS status FROM catalog_items WHERE title_internal LIKE 'seed-%'",
            )
            flags = await conn.fetch("SELECT key, value FROM feature_flags")
            admins = await conn.fetchval(
                "SELECT count(*) FROM users WHERE email = 'admin@jplearn.local'",
            )
            roles = await conn.fetchval(
                """
                SELECT count(*) FROM user_roles r
                JOIN users u ON u.id = r.user_id
                WHERE u.email = 'admin@jplearn.local'
                """,
            )
            return list(items), list(flags), admins, roles
        finally:
            await conn.close()

    items, flags, admins, roles = asyncio.run(read())

    assert admins == 1, "re-seeding duplicated the admin user"
    assert roles == 2, "admin should hold exactly admin + teacher"
    assert len(flags) == 4 and all(row["value"] is False for row in flags)
    # FR-CAT-002 / #39: seed must not publish an item that has no media.
    assert {row["status"] for row in items} == {"draft"}


def test_fr_neg_scanner_flags_a_python_file() -> None:
    """FR-NEG-004 negative guard, ported from schema.guard.spec.ts.

    The scanner itself stays repo tooling (it must also read .ts/.tsx for web and
    mobile), so this drives it through the workspace tsx binary.
    """
    repo = Path(__file__).resolve().parents[3]
    tsx = repo / "node_modules" / ".bin" / "tsx"
    if not tsx.exists():
        pytest.skip("workspace tsx binary missing; run the install first")

    probe = repo / "apps" / "api-python" / "src" / "jplearn_api" / "_fr_neg_probe.py"
    probe.write_text("vocabulary_score = 1\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [str(tsx), "scripts/assert-no-textbook.ts"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, "scanner should fail on a banned column in a .py file"
        assert "vocabulary_score" in result.stderr + result.stdout
    finally:
        probe.unlink(missing_ok=True)
