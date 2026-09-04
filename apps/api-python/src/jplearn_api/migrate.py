"""Migration CLI. Alembic owns DDL as of ADR-004 (replaces `prisma migrate deploy`).

    jplearn-migrate upgrade [revision]   # default: head
    jplearn-migrate downgrade <revision>
    jplearn-migrate stamp <revision>     # adopt an existing Prisma-built database
    jplearn-migrate current

Reads DATABASE_URL from the environment. The Alembic tree and schema baseline
ship inside the package resources so the command works reliably from any working
directory or inside container artifacts without filesystem depth assumptions.
"""

from __future__ import annotations

import importlib.resources
import json
import os
from pathlib import Path
import sys
from typing import Any

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def load_baseline_schema(explicit_path: Path | str | None = None) -> dict[str, Any]:
    """Load baseline schema JSON from explicit path, package resources, or repo fallback.
    Fails closed if missing or malformed.
    """
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            raise RuntimeError(f"Baseline schema not found at explicit path: {p}")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as err:
            raise RuntimeError(f"Malformed baseline schema at {p}: {err}") from err

    # 1. Environment variable override
    env_path = os.environ.get("SCHEMA_BASELINE_PATH")
    if env_path:
        p = Path(env_path)
        if not p.exists():
            raise RuntimeError(f"SCHEMA_BASELINE_PATH set to '{env_path}' but file does not exist")
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as err:
            raise RuntimeError(f"Malformed baseline schema at {p}: {err}") from err

    # 2. Packaged resource
    try:
        resource = importlib.resources.files("jplearn_api.resources").joinpath("adr-004-schema-baseline.json")
        if resource.is_file():
            return json.loads(resource.read_text(encoding="utf-8"))
    except Exception:
        pass

    # 3. Walk parent directories looking for docs/qa/adr-004-schema-baseline.json
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = curr / "docs" / "qa" / "adr-004-schema-baseline.json"
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception as err:
                raise RuntimeError(f"Malformed baseline schema at {candidate}: {err}") from err
        if curr.parent == curr:
            break
        curr = curr.parent

    raise RuntimeError("Baseline schema resource 'adr-004-schema-baseline.json' could not be found")


def resolve_database_url(explicit: str | None = None) -> str | None:
    """Environment first, then a local .env — same precedence as Settings."""
    if explicit:
        return explicit
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")
    return None


def alembic_config(database_url: str | None = None) -> Config:
    url = resolve_database_url(database_url)
    if not url:
        raise RuntimeError("DATABASE_URL is required to run migrations")
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


def upgrade(database_url: str | None = None, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)


def downgrade(revision: str, database_url: str | None = None) -> None:
    env = (os.environ.get("ENVIRONMENT") or "").lower().strip()
    is_destructive = revision.lower() in ("base", "-1", "-all") or revision.startswith("-")
    if is_destructive:
        allow = os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE", "").lower() in ("true", "1", "yes")
        if env not in ("local", "test") and not allow:
            raise RuntimeError(
                f"Destructive downgrade to {revision} is blocked in '{env or 'unknown'}' environment "
                f"without ALLOW_DESTRUCTIVE_DOWNGRADE=true"
            )
    command.downgrade(alembic_config(database_url), revision)


def stamp(
    revision: str = "head",
    database_url: str | None = None,
    *,
    verify_baseline: bool = True,
    baseline_path: Path | str | None = None,
) -> None:
    url = resolve_database_url(database_url)
    if not url:
        raise RuntimeError("DATABASE_URL is required to run migrations")

    if verify_baseline and revision in ("0001_prisma_baseline", "head"):
        import asyncio
        from jplearn_api.schema_snapshot import diff, snapshot_url

        expected = load_baseline_schema(baseline_path)
        actual = asyncio.run(snapshot_url(url))

        if not actual.get("tables"):
            raise RuntimeError(
                f"Refusing to stamp {revision} on empty database: "
                "empty databases must use 'upgrade head' instead of adoption stamp"
            )

        problems = diff(expected, actual)
        if problems:
            diff_msg = "\n".join(problems)
            raise RuntimeError(
                f"Refusing to stamp {revision}: live schema diverges from baseline:\n{diff_msg}"
            )

    command.stamp(alembic_config(url), revision)


def current(database_url: str | None = None) -> None:
    command.current(alembic_config(database_url), verbose=True)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    action = args.pop(0) if args else "upgrade"
    try:
        if action == "upgrade":
            upgrade(revision=args[0] if args else "head")
        elif action == "downgrade":
            if not args:
                print("downgrade requires a revision", file=sys.stderr)
                return 2
            downgrade(args[0])
        elif action == "stamp":
            stamp(args[0] if args else "head")
        elif action == "current":
            current()
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Exception as error:  # surface a one-line reason, not a stack trace
        print(f"migrate {action} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
