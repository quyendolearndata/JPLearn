"""Media use case handlers (Pure Python, protocol-based)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import logging
from pathlib import Path
import re
from time import time
from typing import Any
from uuid import uuid4

from jplearn_api.application.ports.repositories import MediaRepository
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.read_models import MediaAssetStaffDTO
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.domain.media import MediaAsset
from jplearn_api.domain.range_parser import RangeNotSatisfiableError, parse_byte_range
from jplearn_api.signed_url import sign_hls_url, sign_media_url

logger = logging.getLogger("jplearn.media")

HLS_MANIFEST = "index.m3u8"
HLS_CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".m4s": "video/iso.segment",
    ".mp4": "video/mp4",
    ".vtt": "text/vtt",
}
HLS_FILE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
COMMIT_CANCELLATION_GRACE_SECONDS = 5.0


def _signed_playback(asset_id: str, base_url: str, secret: str) -> str:
    return sign_media_url(
        asset_id=asset_id,
        base_url=base_url,
        secret=secret,
        now_sec=int(time()),
    )


def _signed_hls(asset_id: str, base_url: str, secret: str) -> str:
    return sign_hls_url(
        asset_id=asset_id,
        base_url=base_url,
        secret=secret,
        now_sec=int(time()),
    )


def to_staff_dto(asset: MediaAsset, base_url: str, secret: str) -> MediaAssetStaffDTO:
    return MediaAssetStaffDTO(
        id=asset.id,
        catalog_item_id=asset.catalog_item_id,
        storage_key=asset.storage_key,
        playback_url=_signed_playback(asset.id, base_url, secret),
        hls_url=_signed_hls(asset.id, base_url, secret) if asset.hls_url else None,
        mime=asset.mime,
    )


async def handle_upload_media(
    catalog_item_id: str,
    first_chunk: bytes,
    stream: AsyncIterator[bytes],
    filename: str,
    content_type: str,
    uow: AsyncUnitOfWork,
    media_repo: MediaRepository,
    storage: StoragePort,
    base_url: str,
    secret: str,
    *,
    _pre_commit_hook: Any = None,
    _grace_seconds: float = COMMIT_CANCELLATION_GRACE_SECONDS,
) -> MediaAssetStaffDTO:
    """Upload media file with strict 3-state commit outcome machine."""
    item_exists = await media_repo.catalog_item_exists(catalog_item_id)
    if not item_exists:
        raise EntityNotFoundError("Catalog item not found")

    # 1. Validate file extension and MIME per ADR-005 BA decision
    norm_filename = (filename or "").lower().strip()
    if not norm_filename.endswith(".mp4"):
        raise InvalidDomainStateError(f"Invalid file extension: expected '.mp4', got '{Path(norm_filename).suffix}'")
    if content_type != "video/mp4":
        raise InvalidDomainStateError(f"Invalid MIME type: expected 'video/mp4', got '{content_type}'")

    # 2. Inspect first chunk for MP4 magic bytes (ftyp box at offset 4)
    if not first_chunk or len(first_chunk) < 8:
        raise InvalidDomainStateError("File must not be empty and must contain a valid header")
    if first_chunk[4:8] != b"ftyp":
        raise InvalidDomainStateError("Invalid MP4 file signature: expected 'ftyp' box")

    asset_id = str(uuid4())
    temp_key = f"{asset_id}.part"
    final_key = f"{asset_id}.bin"

    async def full_stream() -> AsyncIterator[bytes]:
        yield first_chunk
        async for chunk in stream:
            yield chunk

    # 3. Stream to staging key and promote
    try:
        await storage.stage_stream(temp_key, full_stream())
    except ValueError as exc:
        raise InvalidDomainStateError(str(exc)) from exc

    try:
        await storage.promote(temp_key, final_key)
    except BaseException as exc:
        async def _clean_promote() -> None:
            try:
                await storage.delete(temp_key)
            except Exception:
                pass
            try:
                await storage.delete(final_key)
            except Exception:
                pass

        await asyncio.shield(_clean_promote())
        if isinstance(exc, Exception):
            raise RuntimeError("Failed to store media file") from exc
        raise

    # 4. Record staging and run pre-commit hooks
    asset = MediaAsset(
        id=asset_id,
        catalog_item_id=catalog_item_id,
        storage_key=final_key,
        playback_url=f"{base_url}/media/{asset_id}",
        mime="video/mp4",
    )
    await media_repo.add(asset)

    if _pre_commit_hook is not None:
        try:
            hook_res = _pre_commit_hook()
            if asyncio.iscoroutine(hook_res):
                await hook_res
        except BaseException:
            rb_ok = False
            try:
                await uow.rollback()
                rb_ok = True
            except Exception as rb_exc:
                logger.warning(
                    "media_upload_commit_outcome_unknown",
                    extra={
                        "asset_id": asset_id,
                        "catalog_item_id": catalog_item_id,
                        "final_key": final_key,
                        "reason": f"rollback_failed: {type(rb_exc).__name__}",
                    },
                )

            if rb_ok:
                try:
                    await storage.delete(final_key)
                except Exception:
                    pass
            raise

    # 5. Commit with outcome machine
    commit_task = asyncio.create_task(uow.commit())
    committed = False
    try:
        await asyncio.shield(commit_task)
        committed = True
    except asyncio.CancelledError:
        try:
            await asyncio.wait_for(
                asyncio.shield(commit_task),
                timeout=_grace_seconds,
            )
            committed = True
        except TimeoutError:
            commit_task.cancel()
        except asyncio.CancelledError:
            commit_task.cancel()
        except Exception:
            pass

        if not committed:
            while not commit_task.done():
                try:
                    await asyncio.shield(commit_task)
                except asyncio.CancelledError:
                    if not commit_task.done():
                        continue
                except Exception:
                    break
            try:
                commit_task.result()
            except BaseException:
                pass

            rollback_error = None
            try:
                await uow.rollback()
            except Exception as exc:
                rollback_error = exc
            reason = "cancelled_during_commit"
            if rollback_error is not None:
                reason += f"_rollback_failed:{type(rollback_error).__name__}"
            logger.warning(
                "media_upload_commit_outcome_unknown",
                extra={
                    "asset_id": asset_id,
                    "catalog_item_id": catalog_item_id,
                    "final_key": final_key,
                    "reason": reason,
                },
            )
        raise
    except Exception as exc:
        is_integrity_error = "IntegrityError" in [cls.__name__ for cls in type(exc).__mro__]
        if is_integrity_error:
            rb_ok = False
            try:
                await uow.rollback()
                rb_ok = True
            except Exception as rb_exc:
                logger.warning(
                    "media_upload_commit_outcome_unknown",
                    extra={
                        "asset_id": asset_id,
                        "catalog_item_id": catalog_item_id,
                        "final_key": final_key,
                        "reason": f"rollback_failed: {type(rb_exc).__name__}",
                    },
                )
            if rb_ok:
                try:
                    await storage.delete(final_key)
                except Exception:
                    pass
        else:
            logger.warning(
                "media_upload_commit_outcome_unknown",
                extra={
                    "asset_id": asset_id,
                    "catalog_item_id": catalog_item_id,
                    "final_key": final_key,
                    "reason": type(exc).__name__,
                },
            )
            async def _cleanup_uow() -> None:
                try:
                    await uow.rollback()
                except Exception:
                    pass
            await asyncio.shield(_cleanup_uow())
        raise

    return to_staff_dto(asset, base_url, secret)


async def handle_register_hls(
    asset_id: str,
    uow: AsyncUnitOfWork,
    media_repo: MediaRepository,
    storage: StoragePort,
    base_url: str,
    secret: str,
) -> MediaAssetStaffDTO:
    """Register HLS manifest for an existing media asset."""
    asset = await media_repo.get_by_id(asset_id)
    if asset is None:
        raise EntityNotFoundError("Media asset not found")

    manifest_key = f"hls/{asset_id}/{HLS_MANIFEST}"
    exists = await storage.exists(manifest_key)
    if not exists:
        raise InvalidDomainStateError("HLS manifest missing on disk; run scripts/transcode-hls.sh for this asset first")

    asset.hls_url = f"{base_url}/media/{asset_id}/hls/{HLS_MANIFEST}"
    async with uow:
        await media_repo.update(asset)
        await uow.commit()

    return to_staff_dto(asset, base_url, secret)


async def handle_get_media(asset_id: str, media_repo: MediaRepository) -> MediaAsset:
    """Load media asset metadata."""
    asset = await media_repo.get_by_id(asset_id)
    if asset is None:
        raise EntityNotFoundError("Media asset not found")
    return asset


async def handle_stream_media(
    asset_id: str,
    media_repo: MediaRepository,
    storage: StoragePort,
    range_header: str | None = None,
) -> tuple[AsyncIterator[bytes], int, str, int, dict[str, str]]:
    """Retrieve async byte stream and headers for MP4 playback."""
    asset = await handle_get_media(asset_id, media_repo)
    if not await storage.exists(asset.storage_key):
        raise EntityNotFoundError("Media asset not found")

    meta = await storage.get_metadata(asset.storage_key)
    total_size = meta.size

    range_spec = parse_byte_range(range_header, total_size)
    if range_spec is not None:
        start, end, length = range_spec
        stream_iter = await storage.open_read_range(asset.storage_key, start, length)
        status_code = 206
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }
    else:
        stream_iter = await storage.open_read(asset.storage_key)
        status_code = 200
        headers = {
            "Content-Length": str(total_size),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }

    return stream_iter, total_size, asset.mime, status_code, headers


async def handle_stream_hls(
    storage: StoragePort,
    asset_id: str,
    file: str,
    range_header: str | None = None,
) -> tuple[AsyncIterator[bytes], int, str, int, dict[str, str]]:
    """Retrieve async stream for HLS manifest or segment."""
    if not HLS_FILE_PATTERN.match(file) or ".." in file or "/" in file or "\\" in file:
        raise InvalidDomainStateError("Invalid HLS file name")
    suffix = Path(file).suffix.lower()
    content_type = HLS_CONTENT_TYPES.get(suffix)
    if content_type is None:
        raise InvalidDomainStateError("Unsupported HLS file type")
    key = f"hls/{asset_id}/{file}"
    if not await storage.exists(key):
        raise EntityNotFoundError("HLS file not found")

    meta = await storage.get_metadata(key)
    total_size = meta.size

    is_manifest = suffix == ".m3u8"
    range_spec = None if is_manifest else parse_byte_range(range_header, total_size)

    if range_spec is not None:
        start, end, length = range_spec
        stream_iter = await storage.open_read_range(key, start, length)
        status_code = 206
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }
    else:
        stream_iter = await storage.open_read(key)
        status_code = 200
        headers = {
            "Content-Length": str(total_size),
            "Accept-Ranges": "bytes" if not is_manifest else "none",
            "X-Content-Type-Options": "nosniff",
        }

    return stream_iter, total_size, content_type, status_code, headers
