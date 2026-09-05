"""Media use case handlers (Pure Python, protocol-based)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from enum import Enum
import logging
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from jplearn_api.application.ports.repositories import MediaRepository
from jplearn_api.application.ports.security import MediaUrlSigner
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork, UnitOfWorkFactory
from jplearn_api.application.read_models import ByteRange, MediaAssetStaffDTO, MediaStreamDTO
from jplearn_api.domain.errors import (
    DeterministicAbortError,
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.domain.media import MediaAsset
from jplearn_api.domain.range_parser import RangeNotSatisfiableError, parse_byte_range

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


def to_staff_dto(
    asset: MediaAsset,
    signer: MediaUrlSigner,
) -> MediaAssetStaffDTO:
    """Project domain MediaAsset into staff DTO with URLs signed by the injected MediaUrlSigner."""
    playback_url = signer.sign_playback_url(asset.id)
    hls_url = signer.sign_hls_url(asset.id) if asset.hls_url else None

    return MediaAssetStaffDTO(
        id=asset.id,
        catalog_item_id=asset.catalog_item_id,
        storage_key=asset.storage_key,
        playback_url=playback_url,
        hls_url=hls_url,
        mime=asset.mime,
    )


class UploadCommitOutcome(str, Enum):
    COMMITTED = "committed"
    ROLLBACK_CONFIRMED = "rollback_confirmed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class UploadTransactionCoordinator:
    """Single coordinator managing Scope 3 write UoW lifecycle, transaction outcome,
    and storage compensation under cancellation and error conditions.
    """

    def __init__(
        self,
        uow: AsyncUnitOfWork,
        storage: StoragePort,
        asset_id: str,
        catalog_item_id: str,
        final_key: str,
        grace_seconds: float,
    ) -> None:
        self.uow = uow
        self.storage = storage
        self.asset_id = asset_id
        self.catalog_item_id = catalog_item_id
        self.final_key = final_key
        self.grace_seconds = grace_seconds
        self.outcome = "pending"  # pending | committed | rollback_confirmed | outcome_unknown
        self.cleanup_task: asyncio.Task[None] | None = None

    async def settle_rollback_and_cleanup(self, reason: str) -> None:
        """Execute rollback and storage deletion shielded from cancellation.
        Drains cleanup task to completion even if caller task receives repeated cancellations.
        """
        if self.outcome == "committed":
            return

        if self.cleanup_task is None:
            async def _run_cleanup() -> None:
                rb_ok = getattr(self.uow, "rolled_back", False)
                if not rb_ok and getattr(self.uow, "committed", False):
                    self.outcome = "committed"
                    return

                if not rb_ok:
                    try:
                        await self.uow.rollback()
                        rb_ok = getattr(self.uow, "rolled_back", True)
                    except Exception as rb_exc:
                        self.outcome = "outcome_unknown"
                        logger.warning(
                            "media_upload_commit_outcome_unknown",
                            extra={
                                "asset_id": self.asset_id,
                                "catalog_item_id": self.catalog_item_id,
                                "final_key": self.final_key,
                                "outcome": "outcome_unknown",
                                "reason": f"rollback_failed_{reason}: {type(rb_exc).__name__}",
                                "task_state": "rollback_exception",
                            },
                        )
                        return

                if rb_ok:
                    self.outcome = "rollback_confirmed"
                    try:
                        await self.storage.delete(self.final_key)
                    except Exception as del_exc:
                        logger.warning(
                            "media_cleanup_failed",
                            extra={
                                "asset_id": self.asset_id,
                                "catalog_item_id": self.catalog_item_id,
                                "final_key": self.final_key,
                                "outcome": "rollback_confirmed",
                                "reason": f"storage_delete_failed_{reason}: {type(del_exc).__name__}",
                                "task_state": "delete_exception",
                            },
                        )

            self.cleanup_task = asyncio.create_task(_run_cleanup())
            self.uow.own_cleanup(self.cleanup_task)

        # Drain cleanup_task with timeout budget, absorbing outer cancellations
        start_t = asyncio.get_event_loop().time()
        while not self.cleanup_task.done():
            elapsed = asyncio.get_event_loop().time() - start_t
            remaining = max(0.01, self.grace_seconds - elapsed)
            try:
                await asyncio.wait_for(asyncio.shield(self.cleanup_task), timeout=remaining)
            except TimeoutError:
                self.outcome = "outcome_unknown"
                logger.warning(
                    "media_upload_commit_outcome_unknown",
                    extra={
                        "asset_id": self.asset_id,
                        "catalog_item_id": self.catalog_item_id,
                        "final_key": self.final_key,
                        "outcome": "outcome_unknown",
                        "reason": f"cleanup_drain_timeout_{reason}",
                        "task_state": "drain_timeout",
                    },
                )
                self.cleanup_task.cancel()
                # Cancellation is only a request. The UoW retains ownership and
                # defers close until the task has actually terminated.
                break
            except asyncio.CancelledError:
                continue
            except Exception:
                break

        if self.cleanup_task.done() and not self.cleanup_task.cancelled():
            try:
                self.cleanup_task.result()
            except Exception:
                pass


async def handle_upload_media(
    catalog_item_id: str,
    first_chunk: bytes,
    stream: AsyncIterator[bytes],
    filename: str,
    content_type: str,
    uow_factory: UnitOfWorkFactory,
    storage: StoragePort,
    signer: MediaUrlSigner,
    *,
    id_generator: Callable[[], str] = lambda: str(uuid4()),
    _pre_commit_hook: Any = None,
    _grace_seconds: float | None = None,
    _staging_barrier: Any = None,
) -> MediaAssetStaffDTO:
    """Upload media file with strict 3-scope transaction isolation and scoped UoW factories."""
    if not callable(uow_factory):
        raise ValueError("uow_factory must be a callable returning an AsyncUnitOfWork")
    if storage is None:
        raise ValueError("storage is required")
    if signer is None:
        raise ValueError("MediaUrlSigner is required")

    resolved_grace_seconds = (
        _grace_seconds if _grace_seconds is not None else COMMIT_CANCELLATION_GRACE_SECONDS
    )

    # Scope 1: Preflight read check (short-lived read scope, closed immediately)
    preflight_uow = uow_factory()
    async with preflight_uow:
        item_exists = await preflight_uow.media.catalog_item_exists(catalog_item_id)
        if not item_exists:
            raise EntityNotFoundError("Catalog item not found")
    # Scope 1 exited and closed! Preflight connection returned to pool.

    # Scope 2: Stream & Stage & Promote (Zero DB connections or transactions held)
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

    asset_id = id_generator()
    temp_key = f"{asset_id}.part"
    final_key = f"{asset_id}.bin"

    async def full_stream() -> AsyncIterator[bytes]:
        yield first_chunk
        if _staging_barrier is not None:
            barrier_res = _staging_barrier()
            if asyncio.iscoroutine(barrier_res):
                await barrier_res
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

    # Scope 3: Metadata write in a fresh UoW
    write_uow = None
    try:
        write_uow = uow_factory()
    except BaseException:
        # Factory failed before UoW creation: no DB transaction opened, no mutations
        try:
            await storage.delete(final_key)
        except Exception as del_exc:
            logger.warning(
                "media_cleanup_failed",
                extra={
                    "asset_id": asset_id,
                    "catalog_item_id": catalog_item_id,
                    "final_key": final_key,
                    "outcome": "rollback_confirmed",
                    "reason": f"storage_delete_failed_on_factory_error: {type(del_exc).__name__}",
                    "task_state": "factory_failed",
                },
            )
        raise

    coordinator = UploadTransactionCoordinator(
        uow=write_uow,
        storage=storage,
        asset_id=asset_id,
        catalog_item_id=catalog_item_id,
        final_key=final_key,
        grace_seconds=resolved_grace_seconds,
    )

    uow_entered = False
    abort_reason: str | None = None
    try:
        async with write_uow:
            uow_entered = True
            target_repo = write_uow.media

            # Revalidate catalog reference at write boundary
            try:
                catalog_exists = await target_repo.catalog_item_exists(catalog_item_id)
            except BaseException:
                abort_reason = "recheck_query_failed"
                await coordinator.settle_rollback_and_cleanup(abort_reason)
                raise

            if not catalog_exists:
                abort_reason = "catalog_missing"
                await coordinator.settle_rollback_and_cleanup(abort_reason)
                raise EntityNotFoundError("Catalog item not found")

            # 4. Record staging and run pre-commit hooks
            try:
                playback_raw = (
                    signer.playback_url(asset_id)
                    if hasattr(signer, "playback_url")
                    else f"/media/{asset_id}"
                )
                asset = MediaAsset(
                    id=asset_id,
                    catalog_item_id=catalog_item_id,
                    storage_key=final_key,
                    playback_url=playback_raw,
                    mime="video/mp4",
                )
                await target_repo.add(asset)

                if _pre_commit_hook is not None:
                    hook_res = _pre_commit_hook()
                    if asyncio.iscoroutine(hook_res):
                        await hook_res
            except BaseException:
                abort_reason = "pre_commit_failed"
                await coordinator.settle_rollback_and_cleanup(abort_reason)
                raise

            # 5. Commit with outcome machine
            commit_task = asyncio.create_task(write_uow.commit())
            try:
                await asyncio.shield(commit_task)
                coordinator.outcome = "committed"
            except asyncio.CancelledError:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(commit_task),
                        timeout=resolved_grace_seconds,
                    )
                    coordinator.outcome = "committed"
                except TimeoutError:
                    commit_task.cancel()
                except asyncio.CancelledError:
                    commit_task.cancel()
                except Exception:
                    pass

                if coordinator.outcome != "committed":
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

                if coordinator.outcome != "committed":
                    coordinator.outcome = "outcome_unknown"
                    rollback_error = None
                    try:
                        await write_uow.rollback()
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
                            "outcome": "outcome_unknown",
                            "reason": reason,
                            "task_state": "commit_cancelled",
                        },
                    )
                raise
            except Exception as exc:
                is_deterministic_abort = isinstance(exc, DeterministicAbortError) or getattr(exc, "is_deterministic_abort", False)
                if is_deterministic_abort:
                    abort_reason = "deterministic_abort"
                    await coordinator.settle_rollback_and_cleanup(abort_reason)
                else:
                    coordinator.outcome = "outcome_unknown"
                    logger.warning(
                        "media_upload_commit_outcome_unknown",
                        extra={
                            "asset_id": asset_id,
                            "catalog_item_id": catalog_item_id,
                            "final_key": final_key,
                            "outcome": "outcome_unknown",
                            "reason": f"commit_failed:{type(exc).__name__}",
                            "task_state": "commit_exception",
                        },
                    )
                    try:
                        await write_uow.rollback()
                    except Exception:
                        pass
                raise
    except BaseException:
        if not uow_entered and write_uow is not None:
            rb_ok = False
            try:
                await write_uow.rollback()
                rb_ok = True
            except Exception:
                pass
            if rb_ok or getattr(write_uow, "session", None) is None:
                try:
                    await storage.delete(final_key)
                except Exception as del_exc:
                    logger.warning(
                        "media_cleanup_failed",
                        extra={
                            "asset_id": asset_id,
                            "catalog_item_id": catalog_item_id,
                            "final_key": final_key,
                            "outcome": "rollback_confirmed",
                            "reason": f"storage_delete_failed_on_enter_error: {type(del_exc).__name__}",
                            "task_state": "enter_failed",
                        },
                    )
        elif uow_entered and coordinator.outcome not in ("committed", "outcome_unknown"):
            await coordinator.settle_rollback_and_cleanup(abort_reason or "unhandled_scope3_exception")
        raise

    return to_staff_dto(asset, signer=signer)


async def handle_register_hls(
    asset_id: str,
    uow: AsyncUnitOfWork,
    storage: StoragePort,
    signer: MediaUrlSigner,
    *,
    media_repo: MediaRepository | None = None,
) -> MediaAssetStaffDTO:
    """Register HLS manifest for an existing media asset."""
    target_repo = media_repo if media_repo is not None else uow.media
    async with uow:
        asset = await target_repo.get_by_id(asset_id)
        if asset is None:
            raise EntityNotFoundError("Media asset not found")

        manifest_key = f"hls/{asset_id}/{HLS_MANIFEST}"
        exists = await storage.exists(manifest_key)
        if not exists:
            raise InvalidDomainStateError("HLS manifest missing on disk; run scripts/transcode-hls.sh for this asset first")

        asset.hls_url = signer.manifest_url(asset_id)
        await target_repo.update(asset)
        await uow.commit()

    return to_staff_dto(asset, signer=signer)


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
) -> MediaStreamDTO:
    """Retrieve media byte stream and range information for MP4 playback."""
    asset = await handle_get_media(asset_id, media_repo)
    if not await storage.exists(asset.storage_key):
        raise EntityNotFoundError("Media asset not found")

    meta = await storage.get_metadata(asset.storage_key)
    total_size = meta.size

    range_spec = parse_byte_range(range_header, total_size)
    if range_spec is not None:
        start, end, length = range_spec
        stream_iter = await storage.open_read_range(asset.storage_key, start, length)
        byte_range = ByteRange(start=start, end=end, length=length, total_size=total_size)
    else:
        stream_iter = await storage.open_read(asset.storage_key)
        byte_range = None

    return MediaStreamDTO(
        content_stream=stream_iter,
        content_type=asset.mime,
        total_size=total_size,
        range=byte_range,
    )


async def handle_stream_hls(
    storage: StoragePort,
    asset_id: str,
    file: str,
    range_header: str | None = None,
) -> MediaStreamDTO:
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
        byte_range = ByteRange(start=start, end=end, length=length, total_size=total_size)
    else:
        stream_iter = await storage.open_read(key)
        byte_range = None

    return MediaStreamDTO(
        content_stream=stream_iter,
        content_type=content_type,
        total_size=total_size,
        range=byte_range,
    )
