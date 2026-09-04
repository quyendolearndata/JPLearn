"""Migration CLI. Alembic owns DDL as of ADR-004 (replaces `prisma migrate deploy`).

    jplearn-migrate upgrade [revision]   # default: head
    jplearn-migrate downgrade <revision>
    jplearn-migrate stamp <revision>     # adopt an existing Prisma-built database
    jplearn-migrate current

Reads DATABASE_URL from the environment. The Alembic tree ships inside the
package so the command works from any working directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config

BASELINE_PATH = Path(__file__).resolve().parents[4] / "docs" / "qa" / "adr-004-schema-baseline.json"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


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
    env = (os.environ.get("ENVIRONMENT") or "development").lower()
    if revision.lower() in ("base", "-1", "-all") and env in ("staging", "production"):
        allow = os.environ.get("ALLOW_DESTRUCTIVE_DOWNGRADE", "").lower() in ("true", "1", "yes")
        if not allow:
            raise RuntimeError(
                f"Destructive downgrade to {revision} is blocked in {env} environment without ALLOW_DESTRUCTIVE_DOWNGRADE=true"
            )
    command.downgrade(alembic_config(database_url), revision)


def stamp(revision: str, database_url: str | None = None, *, verify_baseline: bool = True) -> None:
    url = resolve_database_url(database_url)
    if not url:
        raise RuntimeError("DATABASE_URL is required to run migrations")

    if verify_baseline and revision in ("0001_prisma_baseline", "head") and BASELINE_PATH.exists():
        import asyncio
        from jplearn_api.schema_snapshot import diff, snapshot_url

        actual = asyncio.run(snapshot_url(url))
        if actual.get("tables"):
            expected = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
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
