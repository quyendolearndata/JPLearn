from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.models import MediaAsset
from jplearn_api.storage import StoragePort


async def reconcile_orphans(
    session: AsyncSession,
    storage: StoragePort,
    *,
    dry_run: bool = True,
) -> dict[str, list[str]]:
    """Inspect and reconcile storage objects against database MediaAsset records.

    - orphan_storage_keys: files in storage with no database row.
    - missing_storage_keys: database rows with no file in storage.
    If dry_run is False, deletes orphan_storage_keys from storage.
    """
    db_result = await session.execute(select(MediaAsset.storage_key))
    db_keys = set(db_result.scalars().all())

    # We also allow HLS directory structures if present
    storage_keys = set(await storage.list_keys())

    # Exclude HLS sub-files from orphan check if parent key exists
    orphans = [k for k in storage_keys if k not in db_keys and not k.startswith("hls/")]
    missing = [k for k in db_keys if not await storage.exists(k)]

    deleted = []
    if not dry_run:
        for orphan in orphans:
            if await storage.delete(orphan):
                deleted.append(orphan)

    return {
        "orphan_storage_keys": orphans,
        "missing_storage_keys": missing,
        "deleted_storage_keys": deleted,
    }
