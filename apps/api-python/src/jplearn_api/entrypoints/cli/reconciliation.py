"""Media storage reconciliation CLI and entrypoint wrapper."""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.media_repository import SqlAlchemyMediaRepository
from jplearn_api.adapters.storage.local import StoragePort
from jplearn_api.application.handlers.reconciliation import (
    DEFAULT_RETENTION_SECONDS,
    handle_reconcile_orphans,
)

logger = logging.getLogger(__name__)


async def reconcile_orphans(
    session: AsyncSession,
    storage: StoragePort,
    *,
    dry_run: bool = True,
    confirm_retention_exceeded: bool = False,
    retention_seconds: float = DEFAULT_RETENTION_SECONDS,
    now: float | None = None,
) -> dict[str, list[str]]:
    """Entrypoint wrapper delegating to pure application reconciliation handler."""
    media_repo = SqlAlchemyMediaRepository(session)
    return await handle_reconcile_orphans(
        media_repo=media_repo,
        storage=storage,
        dry_run=dry_run,
        confirm_retention_exceeded=confirm_retention_exceeded,
        retention_seconds=retention_seconds,
        now=now,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile media storage against database MediaAsset records.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report orphans and missing records without deleting (default: True).",
    )
    parser.add_argument(
        "--execute",
        "--delete",
        dest="dry_run",
        action="store_false",
        help="Execute destructive deletion of eligible orphans older than retention period.",
    )
    parser.add_argument(
        "--confirm-retention-exceeded",
        action="store_true",
        default=False,
        help="Ops confirmation required to delete orphans older than grace window.",
    )
    parser.add_argument(
        "--retention-hours",
        type=float,
        default=24.0,
        help="Grace window retention period in hours (must be >= 24.0, default: 24.0).",
    )
    args = parser.parse_args(argv)
    if args.retention_hours < 24.0 or math.isnan(args.retention_hours) or math.isinf(args.retention_hours):
        parser.error(
            f"--retention-hours must be a finite number >= 24.0 (ADR-005 policy floor); got {args.retention_hours}"
        )
    return args


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.bootstrap import create_app_container, create_media_repository
    from jplearn_api.settings import get_settings

    settings = get_settings()
    container = create_app_container(settings)
    engine, sessionmaker = create_engine_and_sessions(settings)
    try:
        async with sessionmaker() as session:
            media_repo = create_media_repository(session)
            result = await handle_reconcile_orphans(
                media_repo=media_repo,
                storage=container.storage,
                dry_run=args.dry_run,
                confirm_retention_exceeded=args.confirm_retention_exceeded,
                retention_seconds=args.retention_hours * 3600.0,
            )
            print(f"Orphans detected: {len(result['orphan_storage_keys'])}")
            print(f"Protected (within grace): {len(result['protected_orphan_keys'])}")
            print(f"Eligible for deletion: {len(result['eligible_orphan_keys'])}")
            print(f"Unknown metadata (protected): {len(result['unknown_metadata_keys'])}")
            print(f"Missing from storage: {len(result['missing_storage_keys'])}")
            print(f"Deleted: {len(result['deleted_storage_keys'])}")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
