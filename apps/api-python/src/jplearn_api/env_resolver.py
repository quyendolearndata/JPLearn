from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

VALID_ENVIRONMENTS = ("local", "test", "staging", "production")
EnvironmentType = Literal["local", "test", "staging", "production"]


def read_env_file(env_file_path: Path | str | None = None) -> dict[str, str]:
    """Parse key=value pairs from a .env file if it exists."""
    path = Path(env_file_path) if env_file_path else Path.cwd() / ".env"
    result: dict[str, str] = {}
    if path.exists() and path.is_file():
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, separator, value = line.partition("=")
                if separator:
                    key = key.strip()
                    val = value.strip().strip('"').strip("'")
                    result[key] = val
        except Exception:
            pass
    return result


def resolve_environment(
    explicit: str | None = None,
    env_file_path: Path | str | None = None,
    *,
    default: EnvironmentType = "local",
) -> EnvironmentType:
    """Resolve environment following strict precedence:
    1. Explicit argument
    2. ENVIRONMENT environment variable
    3. .env file
    4. Default ("local")

    Rejects any unknown environment not in ('local', 'test', 'staging', 'production').
    """
    raw_env: str | None = None
    if explicit is not None:
        raw_env = explicit.strip().lower()
    elif "ENVIRONMENT" in os.environ:
        raw_env = os.environ["ENVIRONMENT"].strip().lower()
    else:
        env_vars = read_env_file(env_file_path)
        if "ENVIRONMENT" in env_vars:
            raw_env = env_vars["ENVIRONMENT"].strip().lower()
        else:
            raw_env = default

    if raw_env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid environment '{raw_env}': must be one of {list(VALID_ENVIRONMENTS)}"
        )
    return raw_env  # type: ignore[return-value]


def resolve_database_url(
    explicit: str | None = None,
    env_file_path: Path | str | None = None,
) -> str | None:
    """Resolve DATABASE_URL following strict precedence:
    1. Explicit argument
    2. DATABASE_URL environment variable
    3. .env file
    """
    if explicit is not None and explicit.strip():
        return explicit.strip()
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"].strip()
    env_vars = read_env_file(env_file_path)
    if "DATABASE_URL" in env_vars and env_vars["DATABASE_URL"].strip():
        return env_vars["DATABASE_URL"].strip()
    return None


def is_destructive_downgrade_allowed(
    revision: str,
    environment: str | None = None,
    allow_env_var: str | None = None,
) -> tuple[bool, str]:
    """Check whether a migration downgrade is destructive and if it is permitted.
    Returns (is_allowed, reason).

    Destructive revisions include: 'base', '-1', '-all', or any negative relative offset (starts with '-').

    Rules:
    1. Non-destructive downgrades are always allowed.
    2. Missing or unknown environments NEVER allow destructive downgrade (fail closed),
       even if ALLOW_DESTRUCTIVE_DOWNGRADE=true is set.
    3. In local and test environments, destructive downgrade is permitted.
    4. In staging and production environments, destructive downgrade requires
       ALLOW_DESTRUCTIVE_DOWNGRADE to be 'true', '1', or 'yes'.
    """
    is_destructive = revision.lower() in ("base", "-1", "-all") or revision.startswith("-")
    if not is_destructive:
        return True, "Non-destructive downgrade"

    allow = (
        allow_env_var
        if allow_env_var is not None
        else os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE", "")
    ).lower() in ("true", "1", "yes")

    # Resolve environment
    try:
        env = resolve_environment(environment)
    except Exception:
        env = None

    if env not in VALID_ENVIRONMENTS or env is None:
        raw = environment if environment is not None else (os.environ.get("ENVIRONMENT") or "")
        return False, (
            f"Destructive downgrade to {revision} is blocked in '{raw or 'unknown'}' environment: "
            "unknown or missing environment cannot perform destructive downgrades"
        )

    if env in ("local", "test"):
        return True, f"Destructive downgrade permitted in '{env}' environment"

    if not allow:
        return False, (
            f"Destructive downgrade to {revision} is blocked in '{env}' environment "
            "without ALLOW_DESTRUCTIVE_DOWNGRADE=true"
        )

    return True, f"Destructive downgrade permitted in '{env}' environment with ALLOW_DESTRUCTIVE_DOWNGRADE=true"
