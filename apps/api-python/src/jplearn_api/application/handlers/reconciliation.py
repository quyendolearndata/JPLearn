"""Reconciliation application handler (Pure Python, protocol-based)."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable

from jplearn_api.application.ports.repositories import MediaRepository
from jplearn_api.application.ports.storage import StoragePort

logger = logging.getLogger("jplearn.reconciliation")

DEFAULT_RETENTION_SECONDS = 24 * 3600.0  # 24-hour grace window per ADR-005 BA decision
MIN_RETENTION_SECONDS = 24 * 3600.0  # Strict policy floor


async def handle_reconcile_orphans(
    media_repo: MediaRepository,
    storage: StoragePort,
    *,
    dry_run: bool = True,
    confirm_retention_exceeded: bool = False,
    retention_seconds: float = DEFAULT_RETENTION_SECONDS,
    clock: Callable[[], float] = time.time,
    now: float | None = None,
) -> dict[str, list[str]]:
    """Inspect and reconcile storage objects against database MediaAsset records.

    - orphan_storage_keys: files in storage with no database row.
    - protected_orphan_keys: unreferenced files newer than retention window or with unknown metadata.
    - eligible_orphan_keys: unreferenced files older than retention window with valid metadata.
    - unknown_metadata_keys: unreferenced files where metadata could not be verified or is invalid.
    - missing_storage_keys: database rows with no file in storage.
    - deleted_storage_keys: keys actually removed from storage.
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

    now_ts = clock() if now is None else now
    db_keys = await media_repo.list_all_storage_keys()
    storage_keys = set(await storage.list_keys())

    # Filter out probes, .part files, and HLS sub-segments from orphan candidate pool
    orphans = [
        k
        for k in storage_keys
        if k not in db_keys and not k.startswith("__probe__/") and not k.endswith(".part") and not k.startswith("hls/")
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

        if mtime is None or not isinstance(mtime, (int, float)) or math.isnan(mtime) or math.isinf(mtime):
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
            if await media_repo.storage_key_exists(orphan):
                logger.info("Orphan %s was newly referenced in DB; skipping deletion", orphan)
                continue

            # Recheck metadata & age immediately before deletion
            try:
                curr_meta = await storage.get_metadata(orphan)
                curr_mtime = curr_meta.mtime
            except Exception:
                curr_mtime = None

            current_now = clock() if now is None else now
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
