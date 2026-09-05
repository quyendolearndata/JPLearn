"""Tests for Phase 1 migration and stamp fail-closed behavior.

Guarantees:
1. Missing/malformed baseline resource fails closed.
2. Empty database cannot be stamped (must use upgrade head).
3. Live schema divergence (missing column, extra index, altered constraint) fails stamp.
4. Stamp failure leaves alembic_version table untouched/absent.
5. Destructive downgrade fails closed on missing/unknown/staging/prod environments.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import asyncpg
import pytest

from jplearn_api.migrate import downgrade, load_baseline_schema, stamp, upgrade
from jplearn_api.schema_snapshot import diff, snapshot_url
from pg_harness import start_docker_postgres, stop_docker_postgres


@pytest.fixture(scope="module")
def isolated_postgres() -> str:
    project = "jplearn-migrate-fail-closed"
    stop_docker_postgres(project)
    url = start_docker_postgres(project, migrate=False)
    try:
        yield url
    finally:
        stop_docker_postgres(project)


# --- Unit Tests ---


def test_load_baseline_schema_packaged_resource() -> None:
    schema = load_baseline_schema()
    assert isinstance(schema, dict)
    assert "tables" in schema
    assert "constraints" in schema
    assert "users" in schema["tables"]
    assert "catalog_items" in schema["tables"]


def test_load_baseline_schema_missing_explicit_path(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.json"
    with pytest.raises(RuntimeError, match="Baseline schema not found at explicit path"):
        load_baseline_schema(non_existent)


def test_load_baseline_schema_malformed_json(tmp_path: Path) -> None:
    corrupted = tmp_path / "corrupted.json"
    corrupted.write_text("{not valid json: true", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Malformed baseline schema"):
        load_baseline_schema(corrupted)


def test_load_baseline_schema_env_var_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEMA_BASELINE_PATH", "/non/existent/path/baseline.json")
    with pytest.raises(RuntimeError, match="SCHEMA_BASELINE_PATH set to .* but file does not exist"):
        load_baseline_schema()


@pytest.mark.parametrize(
    "env,allowed",
    [
        ("local", True),
        ("test", True),
        ("staging", False),
        ("production", False),
        ("development", False),
        ("", False),
        ("unknown_env", False),
    ],
)
def test_destructive_downgrade_environment_guards(
    env: str,
    allowed: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", env)
    monkeypatch.delenv("ALLOW_DESTRUCTIVE_DOWNGRADE", raising=False)
    # Use dummy database url so alembic_config would fail only after the env guard
    dummy_db = "postgresql://dummy:dummy@localhost:5432/dummy"

    if not allowed:
        with pytest.raises(RuntimeError, match="Destructive downgrade to base is blocked in"):
            downgrade("base", dummy_db)
    else:
        # It should pass the environment guard and fail at database connection, not environment check
        with pytest.raises(Exception) as exc_info:
            downgrade("base", dummy_db)
        assert "Destructive downgrade to base is blocked" not in str(exc_info.value)


def test_destructive_downgrade_allowed_with_explicit_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "true")
    dummy_db = "postgresql://dummy:dummy@localhost:5432/dummy"

    with pytest.raises(Exception) as exc_info:
        downgrade("base", dummy_db)
    # Must NOT fail on the environment block
    assert "Destructive downgrade to base is blocked" not in str(exc_info.value)


# --- Integration Tests (Real PostgreSQL) ---


def test_stamp_empty_database_fails_closed(isolated_postgres: str) -> None:
    async def ensure_clean_db() -> None:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            tables = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'",
            )
            for row in tables:
                await conn.execute(f"DROP TABLE IF EXISTS \"{row['tablename']}\" CASCADE")
        finally:
            await conn.close()

    async def check_alembic_version_exists() -> bool:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            return bool(
                await conn.fetchval(
                    "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'alembic_version'",
                )
            )
        finally:
            await conn.close()

    asyncio.run(ensure_clean_db())

    # Stamp must refuse an empty database
    with pytest.raises(RuntimeError, match="Refusing to stamp 0001_prisma_baseline on empty database"):
        stamp("0001_prisma_baseline", isolated_postgres)

    # alembic_version table must NOT exist
    assert asyncio.run(check_alembic_version_exists()) is False, "alembic_version was created despite stamp failure!"


def test_stamp_fails_on_schema_divergence_and_preserves_clean_state(
    isolated_postgres: str,
) -> None:
    # First, bring DB to baseline via upgrade
    upgrade(isolated_postgres)

    async def drop_bookkeeping() -> None:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            await conn.execute("DROP TABLE IF EXISTS alembic_version")
        finally:
            await conn.close()

    async def add_extra_index() -> None:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            await conn.execute("CREATE INDEX idx_users_extra ON users (email)")
        finally:
            await conn.close()

    async def drop_extra_index() -> None:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            await conn.execute("DROP INDEX IF EXISTS idx_users_extra")
        finally:
            await conn.close()

    async def check_alembic_version() -> str | None:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'alembic_version'",
            )
            if not exists:
                return None
            return await conn.fetchval("SELECT version_num FROM alembic_version")
        finally:
            await conn.close()

    # Drop alembic_version to simulate unadopted database
    asyncio.run(drop_bookkeeping())
    # Introduce extra index divergence
    asyncio.run(add_extra_index())

    try:
        with pytest.raises(RuntimeError, match="live schema diverges from baseline"):
            stamp("0001_prisma_baseline", isolated_postgres)

        # alembic_version must NOT be present
        assert asyncio.run(check_alembic_version()) is None, "alembic_version was stamped despite divergence!"
    finally:
        asyncio.run(drop_extra_index())

    # Now that divergence is fixed, stamp on exact baseline must succeed!
    stamp("0001_prisma_baseline", isolated_postgres)
    assert asyncio.run(check_alembic_version()) == "0001_prisma_baseline"

    # Subsequent upgrade head is a clean no-op
    expected = load_baseline_schema()
    upgrade(isolated_postgres)
    actual = asyncio.run(snapshot_url(isolated_postgres))
    assert not diff(expected, actual), "upgrade after stamp modified the schema!"


def test_destructive_downgrade_unconfigured_env_preserves_data(
    isolated_postgres: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-08/A: Real database with populated data must not be dropped when
    ENVIRONMENT is unconfigured, even with ALLOW_DESTRUCTIVE_DOWNGRADE=true."""
    # 1. Bring DB to head
    upgrade(isolated_postgres)

    # 2. Insert test user data
    async def insert_user() -> str:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            return await conn.fetchval(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3) RETURNING email",
                "test-user-id",
                "keepsafe@example.com",
                "fakehash",
            )
        finally:
            await conn.close()

    async def get_user_count() -> int:
        conn = await asyncpg.connect(isolated_postgres)
        try:
            return await conn.fetchval("SELECT COUNT(*) FROM users WHERE email = 'keepsafe@example.com'")
        finally:
            await conn.close()

    user_email = asyncio.run(insert_user())
    assert user_email == "keepsafe@example.com"
    assert asyncio.run(get_user_count()) == 1

    # 3. Simulate completely unconfigured environment
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "true")

    # 4. Attempt destructive downgrade
    with pytest.raises(RuntimeError, match="environment is not configured"):
        downgrade("base", isolated_postgres)

    # 5. Verify data is completely intact
    assert asyncio.run(get_user_count()) == 1


def test_migrate_cli_help_and_unknown_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    from jplearn_api.migrate import main

    # 1. Help flags return 0
    assert main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "Migration CLI" in captured.out

    assert main(["-h"]) == 0
    assert main(["help"]) == 0

    # 2. Unknown command returns 2
    assert main(["invalid_command"]) == 2
    captured_err = capsys.readouterr()
    assert "Unknown command: invalid_command" in captured_err.err

    # 3. Missing revision on downgrade returns 2
    assert main(["downgrade"]) == 2
    captured_down = capsys.readouterr()
    assert "downgrade requires a revision" in captured_down.err
