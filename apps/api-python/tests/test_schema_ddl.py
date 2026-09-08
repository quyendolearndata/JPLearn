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

from jplearn_api.adapters.persistence.schema_snapshot import diff, snapshot_url
from jplearn_api.entrypoints.cli.migrate import downgrade, stamp, upgrade
from pg_harness import (
    seed_database,
    start_docker_postgres,
    stop_docker_postgres,
)

BASELINE_0001 = Path(__file__).resolve().parents[3] / "docs" / "qa" / "adr-004-schema-baseline.json"
BASELINE_HEAD = Path(__file__).resolve().parents[3] / "docs" / "qa" / "adr-004-schema-head-0019.json"


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


def test_alembic_schema_matches_head_baseline(alembic_database: str) -> None:
    expected = json.loads(BASELINE_HEAD.read_text(encoding="utf-8"))
    actual = asyncio.run(snapshot_url(alembic_database))
    problems = diff(expected, actual)
    assert not problems, "Alembic schema drifted from the head baseline:\n" + "\n".join(problems)


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
    expected = json.loads(BASELINE_HEAD.read_text(encoding="utf-8"))
    downgrade("base", alembic_database)
    emptied = asyncio.run(snapshot_url(alembic_database))
    assert emptied["tables"] == {}, "downgrade left tables behind"

    upgrade(alembic_database)
    restored = asyncio.run(snapshot_url(alembic_database))
    assert not diff(expected, restored), "re-upgrade did not restore the head baseline schema"


def test_stamp_adopts_a_database_built_before_alembic(alembic_database: str) -> None:
    """ADR-004 adoption path for databases Prisma built (dev, staging).

    Such a database already has the 0001 schema but no `alembic_version`, so
    `upgrade` from base would try to CREATE TYPE on existing types.
    1. A DB with 0001 schema is stamped as '0001_prisma_baseline'.
    2. Trying to stamp 'head' on a 0001 DB is rejected.
    3. `upgrade head` migrates it to 0002, matching the head baseline snapshot.
    4. A DB with 0002 schema can be stamped 'head', but not '0001_prisma_baseline'.
    """
    expected_0001 = json.loads(BASELINE_0001.read_text(encoding="utf-8"))
    expected_head = json.loads(BASELINE_HEAD.read_text(encoding="utf-8"))

    async def drop_bookkeeping() -> None:
        conn = await asyncpg.connect(alembic_database)
        try:
            await conn.execute("DROP TABLE IF EXISTS alembic_version")
        finally:
            await conn.close()

    async def get_revision_and_data() -> tuple[str | None, int]:
        conn = await asyncpg.connect(alembic_database)
        try:
            ver = await conn.fetchval("SELECT version_num FROM alembic_version")
            rev_val = await conn.fetchval("SELECT revision FROM catalog_items LIMIT 1")
            return ver, rev_val
        finally:
            await conn.close()

    # Reset to 0001 state: downgrade base, then upgrade to 0001 only
    downgrade("base", alembic_database)
    upgrade(alembic_database, revision="0001_prisma_baseline")
    actual_0001 = asyncio.run(snapshot_url(alembic_database))
    diff_0001 = diff(expected_0001, actual_0001)
    assert not diff_0001, f"0001 schema drifted from Prisma baseline: {diff_0001}"

    # Seed an item in 0001
    seed_database(alembic_database)

    # Drop alembic_version to simulate an untracked Prisma-built DB
    asyncio.run(drop_bookkeeping())

    # 1. Stamping 'head' on 0001 schema must fail closed
    with pytest.raises(RuntimeError, match="Refusing to stamp head"):
        stamp("head", alembic_database)

    # 2. Stamping '0001_prisma_baseline' must succeed
    stamp("0001_prisma_baseline", alembic_database)

    # 3. Upgrade to head executes 0002
    upgrade(alembic_database)
    actual_head = asyncio.run(snapshot_url(alembic_database))
    diff_head = diff(expected_head, actual_head)
    assert not diff_head, f"Upgraded schema drifted from head baseline: {diff_head}"

    # 4. Confirm data & schema properties
    ver, rev_val = asyncio.run(get_revision_and_data())
    assert ver == "0019_merge_cms_reviews"
    assert rev_val == 1, "Catalog items must have default revision=1 after migration 0002"

    # 5. Drop bookkeeping again to simulate adoption of a 0002 DB
    asyncio.run(drop_bookkeeping())
    # Stamping 0001 on a 0002 DB must fail closed
    with pytest.raises(RuntimeError, match="Refusing to stamp 0001_prisma_baseline"):
        stamp("0001_prisma_baseline", alembic_database)
    # Stamping head on a 0002 DB must succeed
    stamp("head", alembic_database)


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


def test_stamp_fails_when_live_schema_diverges(alembic_database: str) -> None:
    async def add_rogue():
        conn = await asyncpg.connect(alembic_database)
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN rogue_col text")
        finally:
            await conn.close()

    async def drop_rogue():
        conn = await asyncpg.connect(alembic_database)
        try:
            await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS rogue_col")
        finally:
            await conn.close()

    asyncio.run(add_rogue())
    try:
        with pytest.raises(RuntimeError, match="Refusing to stamp 0001_prisma_baseline"):
            stamp("0001_prisma_baseline", alembic_database)
    finally:
        asyncio.run(drop_rogue())


def test_destructive_downgrade_blocked_in_staging_and_production(
    alembic_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_DOWNGRADE", raising=False)

    with pytest.raises(RuntimeError, match="Destructive downgrade to base is blocked"):
        downgrade("base", alembic_database)

    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "true")
    downgrade("base", alembic_database)
    upgrade(alembic_database)


@pytest.mark.parametrize("source_revision", ["0018_hls_bundle_integrity", "0002_cms_reviews"])
def test_merge_upgrade_preserves_each_branch_data(alembic_database, source_revision):
    """Both remote migration lineages upgrade without losing business data."""
    downgrade("base", alembic_database)
    upgrade(alembic_database, revision=source_revision)
    seed_database(alembic_database)

    async def prepare():
        conn = await asyncpg.connect(alembic_database)
        try:
            item_id = await conn.fetchval("SELECT id FROM catalog_items ORDER BY id LIMIT 1")
            user_id = await conn.fetchval("SELECT id FROM users ORDER BY id LIMIT 1")
            await conn.execute("UPDATE catalog_items SET title_internal='preserved merge fixture' WHERE id=$1", item_id)
            if source_revision == "0002_cms_reviews":
                await conn.execute("UPDATE catalog_items SET qa_round=1 WHERE id=$1", item_id)
                await conn.execute(
                    (
                        "INSERT INTO catalog_reviews VALUES ('merge-review', $1, 1, 'approve', "
                        "'preserve original decision', $2, CURRENT_TIMESTAMP)"
                    ),
                    item_id,
                    user_id,
                )
            return item_id
        finally:
            await conn.close()

    item_id = asyncio.run(prepare())
    upgrade(alembic_database)

    async def verify():
        conn = await asyncpg.connect(alembic_database)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0019_merge_cms_reviews"
            assert (
                await conn.fetchval("SELECT title_internal FROM catalog_items WHERE id=$1", item_id)
                == "preserved merge fixture"
            )
            if source_revision == "0002_cms_reviews":
                assert (
                    await conn.fetchval("SELECT notes FROM catalog_reviews WHERE id='merge-review'")
                    == "preserve original decision"
                )
            else:
                assert await conn.fetchval("SELECT count(*) FROM catalog_reviews") == 0
        finally:
            await conn.close()

    asyncio.run(verify())
    assert not diff(json.loads(BASELINE_HEAD.read_text()), asyncio.run(snapshot_url(alembic_database)))
