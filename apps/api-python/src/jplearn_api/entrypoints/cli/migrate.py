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

MIGRATIONS_DIR = Path(importlib.resources.files("jplearn_api").joinpath("migrations"))


def load_baseline_schema(
    revision: str | Path = "0001_prisma_baseline",
    explicit_path: Path | str | None = None,
) -> dict[str, Any]:
    """Load baseline schema JSON from explicit path, package resources, or repo fallback.
    Fails closed if missing or malformed.
    """
    target_path = explicit_path
    target_revision = revision if isinstance(revision, str) else "0001_prisma_baseline"
    if isinstance(revision, Path) or (
        isinstance(revision, str)
        and (revision.endswith(".json") or "/" in revision or "\\" in revision)
    ):
        target_path = revision
        target_revision = "0001_prisma_baseline"

    if target_path:
        p = Path(target_path)
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

    filename = (
        "adr-004-schema-head-0018.json"
        if target_revision in ("head", "0018_hls_bundle_integrity")
        else
        "adr-004-schema-head-0017.json"
        if target_revision == "0017_activity_policy_streak"
        else
        "adr-004-schema-head-0016.json"
        if target_revision == "0016_media_probe"
        else "adr-004-schema-head-0015.json"
        if target_revision == "0015_ai_attempts"
        else "adr-004-schema-head-0014.json"
        if target_revision == "0014_content_source_snapshot"
        else "adr-004-schema-head-0013.json"
        if target_revision == "0013_playback_recovery"
        else "adr-004-schema-head-0012.json"
        if target_revision == "0012_content_jobs"
        else "adr-004-schema-head-0011.json"
        if target_revision in ("0011_ai_quota_and_usage_ledger",)
        else "adr-004-schema-head-0010.json"
        if target_revision in ("0010_transcripts_analysis",)
        else "adr-004-schema-head-0009.json"
        if target_revision in ("0009_activity_and_history",)
        else "adr-004-schema-head-0008.json"
        if target_revision in ("0008_playback_tracking",)
        else "adr-004-schema-head-0007.json"
        if target_revision in ("0007_content_reports",)
        else "adr-004-schema-head-0006.json"
        if target_revision in ("0006_personal_collections",)
        else "adr-004-schema-head-0005.json"
        if target_revision in ("0005_saved_scenes",)
        else "adr-004-schema-head-0004.json"
        if target_revision in ("0004_series",)
        else "adr-004-schema-head-0003.json"
        if target_revision in ("0003_content_versions_and_scenes",)
        else "adr-004-schema-head-0002.json"
        if target_revision in ("0002_session_idem_rev",)
        else "adr-004-schema-baseline.json"
    )


    # 2. Packaged resource
    try:
        resource = importlib.resources.files("jplearn_api.resources").joinpath(filename)
        if resource.is_file():
            return json.loads(resource.read_text(encoding="utf-8"))
    except Exception:
        pass

    # 3. Walk parent directories looking for docs/qa/<filename>
    curr = Path(__file__).resolve().parent
    while True:
        candidate = curr / "docs" / "qa" / filename
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception as err:
                raise RuntimeError(f"Malformed baseline schema at {candidate}: {err}") from err
        if curr.parent == curr:
            break
        curr = curr.parent

    raise RuntimeError(f"Baseline schema resource '{filename}' could not be found")


from jplearn_api.config.env_resolver import (
    is_destructive_downgrade_allowed,
    resolve_database_url,
    resolve_environment,
)

# Re-export for backward compatibility
__all__ = [
    "load_baseline_schema",
    "resolve_database_url",
    "resolve_environment",
    "alembic_config",
    "upgrade",
    "downgrade",
    "stamp",
    "current",
    "main",
]


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
    allowed, reason = is_destructive_downgrade_allowed(revision)
    if not allowed:
        raise RuntimeError(reason)
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

    if verify_baseline and revision in ("0001_prisma_baseline", "head", "0002_session_idem_rev"):
        import asyncio
        from jplearn_api.adapters.persistence.schema_snapshot import diff, snapshot_url

        expected = load_baseline_schema(revision=revision, explicit_path=baseline_path)
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
    if action in ("--help", "-h", "help"):
        print(__doc__)
        return 0
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
            print(f"Unknown command: {action}\n\n{__doc__}", file=sys.stderr)
            return 2
    except Exception as error:  # surface a one-line reason, not a stack trace
        print(f"migrate {action} failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
