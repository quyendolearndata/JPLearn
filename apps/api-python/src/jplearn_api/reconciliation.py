from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.models import MediaAsset
from jplearn_api.storage import StoragePort

DEFAULT_RETENTION_SECONDS = 24 * 3600  # 24-hour grace window per ADR-005 BA decision


async def reconcile_orphans(
    session: AsyncSession,
    storage: StoragePort,
    *,
    dry_run: bool = True,
    force_delete: bool = False,
    confirm_retention_exceeded: bool = False,
    retention_seconds: float = DEFAULT_RETENTION_SECONDS,
    now: float | None = None,
) -> dict[str, list[str]]:
    """Inspect and reconcile storage objects against database MediaAsset records.

    - orphan_storage_keys: files in storage with no database row.
    - protected_orphan_keys: unreferenced files newer than retention window (protected by grace period).
    - eligible_orphan_keys: unreferenced files older than retention window.
    - missing_storage_keys: database rows with no file in storage.
    - deleted_storage_keys: keys actually removed from storage.

    Safety:
    - dry_run=True (default): report-only, never deletes anything.
    - To delete, dry_run=False AND (confirm_retention_exceeded=True OR force_delete=True) must be set.
    - Even when deleting, files younger than retention_seconds are preserved unless force_delete=True.
    """
    now_ts = time.time() if now is None else now
    db_result = await session.execute(select(MediaAsset.storage_key))
    db_keys = set(db_result.scalars().all())

    storage_keys = set(await storage.list_keys())

    # Exclude HLS sub-files from orphan check if parent key exists
    orphans = [k for k in storage_keys if k not in db_keys and not k.startswith("hls/")]
    missing = [k for k in db_keys if not await storage.exists(k)]

    protected_orphans = []
    eligible_orphans = []

    for orphan in orphans:
        try:
            meta = await storage.get_metadata(orphan)
            mtime = meta.mtime
        except Exception:
            mtime = None

        if mtime is not None and (now_ts - mtime) < retention_seconds:
            protected_orphans.append(orphan)
        else:
            eligible_orphans.append(orphan)

    deleted = []
    can_delete = not dry_run and (confirm_retention_exceeded or force_delete)
    if can_delete:
        targets = eligible_orphans if not force_delete else orphans
        for orphan in targets:
            if await storage.delete(orphan):
                deleted.append(orphan)

    return {
        "orphan_storage_keys": orphans,
        "protected_orphan_keys": protected_orphans,
        "eligible_orphan_keys": eligible_orphans,
        "missing_storage_keys": missing,
        "deleted_storage_keys": deleted,
    }


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
        dest="dry_run",
        action="store_false",
        help="Execute destructive deletion of eligible orphans.",
    )
    parser.add_argument(
        "--confirm-retention-exceeded",
        action="store_true",
        default=False,
        help="Ops confirmation required to delete orphans older than grace window.",
    )
    parser.add_argument(
        "--force-delete",
        action="store_true",
        default=False,
        help="Override grace window and delete all unreferenced files.",
    )
    parser.add_argument(
        "--retention-hours",
        type=float,
        default=24.0,
        help="Grace window retention period in hours (default: 24.0).",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    from jplearn_api.db import create_engine_and_sessions
    from jplearn_api.settings import get_settings
    from jplearn_api.storage import LocalFilesystemStorage

    settings = get_settings()
    storage = LocalFilesystemStorage(settings.storage_root)
    engine, sessionmaker = create_engine_and_sessions(settings)
    try:
        async with sessionmaker() as session:
            result = await reconcile_orphans(
                session,
                storage,
                dry_run=args.dry_run,
                force_delete=args.force_delete,
                confirm_retention_exceeded=args.confirm_retention_exceeded,
                retention_seconds=args.retention_hours * 3600,
            )
            print(f"Orphans detected: {len(result['orphan_storage_keys'])}")
            print(f"Protected (within grace): {len(result['protected_orphan_keys'])}")
            print(f"Eligible for deletion: {len(result['eligible_orphan_keys'])}")
            print(f"Missing from storage: {len(result['missing_storage_keys'])}")
            print(f"Deleted: {len(result['deleted_storage_keys'])}")
            return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
