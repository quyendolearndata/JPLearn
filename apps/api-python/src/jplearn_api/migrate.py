"""Migration CLI. Alembic owns DDL as of ADR-004 (replaces `prisma migrate deploy`).

    jplearn-migrate upgrade [revision]   # default: head
    jplearn-migrate downgrade <revision>
    jplearn-migrate stamp <revision>     # adopt an existing Prisma-built database
    jplearn-migrate current

Reads DATABASE_URL from the environment. The Alembic tree ships inside the
package so the command works from any working directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

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
    command.downgrade(alembic_config(database_url), revision)


def stamp(revision: str, database_url: str | None = None) -> None:
    command.stamp(alembic_config(database_url), revision)


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
