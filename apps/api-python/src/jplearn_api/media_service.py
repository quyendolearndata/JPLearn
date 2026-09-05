"""Media service adapter delegating to Clean Architecture application handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.media_repository import SqlAlchemyMediaRepository
from jplearn_api.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWork
from jplearn_api.adapters.storage.range_parser import RangeNotSatisfiable, parse_byte_range
import jplearn_api.application.handlers.media as media_handlers
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.models import MediaAsset
from jplearn_api.schemas import MediaAssetStaff
from jplearn_api.settings import Settings
from jplearn_api.storage import StoragePort

logger = media_handlers.logger
COMMIT_CANCELLATION_GRACE_SECONDS = media_handlers.COMMIT_CANCELLATION_GRACE_SECONDS


def _base_url(settings: Settings) -> str:
    if not settings.api_public_url:
        raise RuntimeError("API_PUBLIC_URL must be set")
    return settings.api_public_url.rstrip("/")


def _secret(settings: Any) -> str:
    return getattr(settings, "media_signing_secret", None) or getattr(settings, "jwt_secret", None) or "default-secret"


async def upload(
    session: AsyncSession,
    settings: Settings,
    storage: StoragePort,
    catalog_item_id: str,
    file: UploadFile,
    *,
    _pre_commit_hook: Any = None,
) -> MediaAssetStaff:
    uow = SqlAlchemyUnitOfWork(session)
    media_repo = SqlAlchemyMediaRepository(session)
    base_url = _base_url(settings)
    secret = _secret(settings)

    filename = (file.filename or "").lower().strip()
    content_type = file.content_type
    first_chunk = await file.read(64 * 1024)

    async def stream_rest() -> AsyncIterator[bytes]:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    try:
        dto = await media_handlers.handle_upload_media(
            catalog_item_id=catalog_item_id,
            first_chunk=first_chunk,
            stream=stream_rest(),
            filename=filename,
            content_type=content_type,
            uow=uow,
            media_repo=media_repo,
            storage=storage,
            base_url=base_url,
            secret=secret,
            _pre_commit_hook=_pre_commit_hook,
            _grace_seconds=COMMIT_CANCELLATION_GRACE_SECONDS,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return MediaAssetStaff(**asdict(dto))


async def get(session: AsyncSession, asset_id: str) -> MediaAsset:
    orm_asset = await session.get(MediaAsset, asset_id)
    if orm_asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return orm_asset


async def register_hls(
    session: AsyncSession,
    settings: Settings,
    storage: StoragePort,
    asset_id: str,
) -> MediaAssetStaff:
    uow = SqlAlchemyUnitOfWork(session)
    media_repo = SqlAlchemyMediaRepository(session)
    base_url = _base_url(settings)
    secret = _secret(settings)
    try:
        dto = await media_handlers.handle_register_hls(
            asset_id=asset_id,
            uow=uow,
            media_repo=media_repo,
            storage=storage,
            base_url=base_url,
            secret=secret,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return MediaAssetStaff(**asdict(dto))


async def stream(
    session: AsyncSession,
    storage: StoragePort,
    asset_id: str,
    range_header: str | None = None,
) -> tuple[AsyncIterator[bytes], int, str, int, dict[str, str]]:
    media_repo = SqlAlchemyMediaRepository(session)
    try:
        return await media_handlers.handle_stream_media(
            asset_id=asset_id,
            media_repo=media_repo,
            storage=storage,
            range_header=range_header,
        )
    except RangeNotSatisfiable:
        raise
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


async def stream_hls(
    storage: StoragePort,
    asset_id: str,
    file: str,
    range_header: str | None = None,
) -> tuple[AsyncIterator[bytes], int, str, int, dict[str, str]]:
    try:
        return await media_handlers.handle_stream_hls(
            storage=storage,
            asset_id=asset_id,
            file=file,
            range_header=range_header,
        )
    except RangeNotSatisfiable:
        raise
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
