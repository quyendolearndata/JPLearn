from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.models import MediaAsset
from jplearn_api.storage import StoragePort

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_SECONDS = 24 * 3600.0  # 24-hour grace window per ADR-005 BA decision
MIN_RETENTION_SECONDS = 24 * 3600.0  # Strict policy floor


async def reconcile_orphans(
    session: AsyncSession,
    storage: StoragePort,
    *,
    dry_run: bool = True,
    confirm_retention_exceeded: bool = False,
    retention_seconds: float = DEFAULT_RETENTION_SECONDS,
    now: float | None = None,
) -> dict[str, list[str]]:
    """Inspect and reconcile storage objects against database MediaAsset records.

    - orphan_storage_keys: files in storage with no database row.
    - protected_orphan_keys: unreferenced files newer than retention window or with unknown metadata.
    - eligible_orphan_keys: unreferenced files older than retention window with valid metadata.
    - unknown_metadata_keys: unreferenced files where metadata could not be verified or is invalid.
    - missing_storage_keys: database rows with no file in storage.
    - deleted_storage_keys: keys actually removed from storage.

    Safety:
    - retention_seconds MUST be a finite number >= 24 hours (86400s). Values below policy or invalid numbers are rejected.
    - dry_run=True (default): report-only, never deletes anything.
    - To delete, dry_run=False AND confirm_retention_exceeded=True must be set.
    - Files with missing, error, non-finite, or future mtime are strictly protected, never eligible.
    - In-flight files (.part), probe files (__probe__/), and HLS segments (hls/) are protected.
    - Immediately prior to deletion, database reference and age are re-checked.
    """
    if (
        not isinstance(retention_seconds, (int, float))
        or math.isnan(retention_seconds)
        or math.isinf(retention_seconds)
        or retention_seconds < MIN_RETENTION_SECONDS
    ):
        raise ValueError(
            f"retention_seconds must be a finite number >= {MIN_RETENTION_SECONDS} (24 hours); got {retention_seconds}"
        )

    now_ts = time.time() if now is None else now
    db_result = await session.execute(select(MediaAsset.storage_key))
    db_keys = set(db_result.scalars().all())

    storage_keys = set(await storage.list_keys())

    # Filter out probes, .part files, and HLS sub-segments from orphan candidate pool
    orphans = [
        k
        for k in storage_keys
        if k not in db_keys
        and not k.startswith("__probe__/")
        and not k.endswith(".part")
        and not k.startswith("hls/")
    ]
    missing = [k for k in db_keys if not await storage.exists(k)]

    protected_orphans: list[str] = []
    eligible_orphans: list[str] = []
    unknown_metadata_keys: list[str] = []

    for orphan in orphans:
        try:
            meta = await storage.get_metadata(orphan)
            mtime = meta.mtime
        except Exception as exc:
            logger.warning("Failed to get metadata for orphan %s: %s", orphan, exc)
            mtime = None

        if (
            mtime is None
            or not isinstance(mtime, (int, float))
            or math.isnan(mtime)
            or math.isinf(mtime)
        ):
            logger.warning("Orphan %s has missing or invalid mtime (%r); marking protected/unknown", orphan, mtime)
            unknown_metadata_keys.append(orphan)
            protected_orphans.append(orphan)
        elif mtime > now_ts:
            logger.warning("Orphan %s has future mtime (%f > now %f); marking protected/unknown", orphan, mtime, now_ts)
            unknown_metadata_keys.append(orphan)
            protected_orphans.append(orphan)
        elif (now_ts - mtime) < retention_seconds:
            protected_orphans.append(orphan)
        else:
            eligible_orphans.append(orphan)

    deleted: list[str] = []
    can_delete = not dry_run and confirm_retention_exceeded
    if can_delete:
        for orphan in list(eligible_orphans):
            # Recheck DB reference immediately before deletion to prevent racing with newly promoted assets
            db_check = await session.execute(
                select(MediaAsset.id).where(MediaAsset.storage_key == orphan)
            )
            if db_check.scalar_one_or_none() is not None:
                logger.info("Orphan %s was newly referenced in DB; skipping deletion", orphan)
                continue

            # Recheck metadata & age immediately before deletion
            try:
                curr_meta = await storage.get_metadata(orphan)
                curr_mtime = curr_meta.mtime
            except Exception:
                curr_mtime = None

            current_now = time.time() if now is None else now
            if (
                curr_mtime is None
                or not isinstance(curr_mtime, (int, float))
                or math.isnan(curr_mtime)
                or math.isinf(curr_mtime)
                or curr_mtime > current_now
                or (current_now - curr_mtime) < retention_seconds
            ):
                logger.info("Orphan %s failed pre-delete age check; skipping deletion", orphan)
                continue

            if await storage.delete(orphan):
                deleted.append(orphan)

    return {
        "orphan_storage_keys": orphans,
        "protected_orphan_keys": protected_orphans,
        "eligible_orphan_keys": eligible_orphans,
        "unknown_metadata_keys": unknown_metadata_keys,
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
        parser.error(f"--retention-hours must be a finite number >= 24.0 (ADR-005 policy floor); got {args.retention_hours}")
    return args


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

