from __future__ import annotations

import os
from pathlib import Path
import pytest

from jplearn_api.env_resolver import (
    is_destructive_downgrade_allowed,
    read_env_file,
    resolve_database_url,
    resolve_environment,
)
from jplearn_api import migrate


def test_resolve_environment_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ENVIRONMENT=staging\nDATABASE_URL=postgresql://from_env_file\n")

    # 1. Default when nothing is provided
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert resolve_environment(env_file_path=tmp_path / "nonexistent.env") == "local"

    # 2. .env file when no env var
    assert resolve_environment(env_file_path=env_file) == "staging"

    # 3. Environment variable overrides .env file
    monkeypatch.setenv("ENVIRONMENT", "test")
    assert resolve_environment(env_file_path=env_file) == "test"

    # 4. Explicit argument overrides environment variable and .env file
    assert resolve_environment("production", env_file_path=env_file) == "production"


def test_resolve_environment_rejects_unknown(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for invalid in ("unknown", "dev", "prod", "", "local_debug", "invalid"):
        with pytest.raises(ValueError, match="Invalid environment"):
            resolve_environment(invalid)


def test_resolve_database_url_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://user:pass@localhost:5432/file_db\n")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    # 1. None when not found
    assert resolve_database_url(env_file_path=tmp_path / "nonexistent.env") is None

    # 2. .env file
    assert resolve_database_url(env_file_path=env_file) == "postgresql://user:pass@localhost:5432/file_db"

    # 3. Env var overrides .env file
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/env_var_db")
    assert resolve_database_url(env_file_path=env_file) == "postgresql://user:pass@localhost:5432/env_var_db"

    # 4. Explicit overrides env var
    assert resolve_database_url("postgresql://explicit_db", env_file_path=env_file) == "postgresql://explicit_db"


def test_is_destructive_downgrade_allowed(monkeypatch: pytest.MonkeyPatch):
    # Non-destructive revisions are always allowed
    allowed, _ = is_destructive_downgrade_allowed("head")
    assert allowed is True
    allowed, _ = is_destructive_downgrade_allowed("0001_prisma_baseline")
    assert allowed is True

    # Destructive revisions:
    for rev in ("base", "-1", "-all", "-2"):
        # 1. Missing or unknown environment is blocked EVEN IF ALLOW_DESTRUCTIVE_DOWNGRADE is set (fail-closed)
        allowed, reason = is_destructive_downgrade_allowed(rev, environment="invalid_env", allow_env_var="true")
        assert allowed is False
        assert "blocked" in reason

        allowed, reason = is_destructive_downgrade_allowed(rev, environment="", allow_env_var="true")
        assert allowed is False
        assert "blocked" in reason

        allowed, reason = is_destructive_downgrade_allowed(rev, environment="development", allow_env_var="true")
        assert allowed is False
        assert "blocked" in reason

        # 2. Staging and production without ALLOW_DESTRUCTIVE_DOWNGRADE are blocked
        allowed, reason = is_destructive_downgrade_allowed(rev, environment="production", allow_env_var="false")
        assert allowed is False
        assert "blocked in 'production'" in reason

        allowed, reason = is_destructive_downgrade_allowed(rev, environment="staging", allow_env_var="")
        assert allowed is False
        assert "blocked in 'staging'" in reason

        # 3. Staging and production with ALLOW_DESTRUCTIVE_DOWNGRADE are permitted
        allowed, reason = is_destructive_downgrade_allowed(rev, environment="production", allow_env_var="true")
        assert allowed is True
        assert "permitted" in reason

        allowed, reason = is_destructive_downgrade_allowed(rev, environment="staging", allow_env_var="yes")
        assert allowed is True
        assert "permitted" in reason

        # 4. Local and test are permitted
        allowed, reason = is_destructive_downgrade_allowed(rev, environment="local")
        assert allowed is True
        assert "permitted" in reason

        allowed, reason = is_destructive_downgrade_allowed(rev, environment="test")
        assert allowed is True
        assert "permitted" in reason


def test_migrate_downgrade_cli_destructive_safety(monkeypatch: pytest.MonkeyPatch):
    # Unknown environment must fail closed even when ALLOW_DESTRUCTIVE_DOWNGRADE=true
    monkeypatch.setenv("ENVIRONMENT", "unknown_env")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "true")

    with pytest.raises(RuntimeError, match="blocked in 'unknown_env' environment"):
        migrate.downgrade("-1")


def test_destructive_downgrade_blocked_when_environment_completely_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """R-08/A: When neither ENVIRONMENT env var nor .env is present,
    destructive downgrade must NOT default to local and must be blocked,
    even when ALLOW_DESTRUCTIVE_DOWNGRADE=true."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "true")
    dummy_env_file = tmp_path / "nonexistent.env"

    for rev in ("base", "-1", "-all"):
        allowed, reason = is_destructive_downgrade_allowed(
            rev,
            environment=None,
            env_file_path=dummy_env_file,
            allow_env_var="true",
        )
        assert allowed is False, f"Expected {rev} to be blocked when environment is unconfigured!"
        assert "unconfigured" in reason or "missing" in reason


