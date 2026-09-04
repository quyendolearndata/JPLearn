from __future__ import annotations

import re
from pathlib import Path
from time import time
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.models import CatalogItem, MediaAsset
from jplearn_api.schemas import MediaAssetStaff
from jplearn_api.settings import Settings
from jplearn_api.signed_url import sign_hls_url, sign_media_url
from jplearn_api.storage import StoragePort

HLS_MANIFEST = "index.m3u8"
HLS_CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".m4s": "video/iso.segment",
    ".mp4": "video/mp4",
    ".vtt": "text/vtt",
}
HLS_FILE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def storage_root(settings: Settings) -> Path:
    if settings.storage_root:
        return Path(settings.storage_root)
    return Path.cwd() / "storage"


def _secret(settings: Settings) -> str:
    return settings.media_signing_secret or settings.jwt_secret


def _base_url(settings: Settings) -> str:
    if not settings.api_public_url:
        raise RuntimeError("API_PUBLIC_URL must be set")
    return settings.api_public_url.rstrip("/")


def _signed_playback(asset_id: str, settings: Settings) -> str:
    return sign_media_url(
        asset_id=asset_id,
        base_url=_base_url(settings),
        secret=_secret(settings),
        now_sec=int(time()),
    )


def _signed_hls(asset_id: str, settings: Settings) -> str:
    return sign_hls_url(
        asset_id=asset_id,
        base_url=_base_url(settings),
        secret=_secret(settings),
        now_sec=int(time()),
    )


def to_staff(asset: MediaAsset, settings: Settings) -> MediaAssetStaff:
    return MediaAssetStaff(
        id=asset.id,
        catalog_item_id=asset.catalog_item_id,
        storage_key=asset.storage_key,
        playback_url=_signed_playback(asset.id, settings),
        hls_url=_signed_hls(asset.id, settings) if asset.hls_url else None,
        mime=asset.mime,
    )


async def upload(
    session: AsyncSession,
    settings: Settings,
    storage: StoragePort,
    catalog_item_id: str,
    file: UploadFile,
) -> MediaAssetStaff:
    item = await session.get(CatalogItem, catalog_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Catalog item not found")

    asset_id = str(uuid4())
    temp_key = f"{asset_id}.part"
    final_key = f"{asset_id}.bin"

    async def file_stream():
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    try:
        await storage.stage_stream(temp_key, file_stream())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        await storage.promote(temp_key, final_key)
    except Exception as exc:
        await storage.delete(temp_key)
        raise HTTPException(status_code=500, detail="Failed to store media file") from exc

    asset = MediaAsset(
        id=asset_id,
        catalog_item_id=catalog_item_id,
        storage_key=final_key,
        playback_url=f"{_base_url(settings)}/media/{asset_id}",
        hls_url=None,
        mime=file.content_type or "application/octet-stream",
    )
    session.add(asset)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete(final_key)
        raise

    return to_staff(asset, settings)


async def get(session: AsyncSession, asset_id: str) -> MediaAsset:
    asset = await session.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return asset


async def register_hls(
    session: AsyncSession,
    settings: Settings,
    storage: StoragePort,
    asset_id: str,
) -> MediaAssetStaff:
    asset = await get(session, asset_id)
    manifest_key = f"hls/{asset_id}/{HLS_MANIFEST}"
    if not await storage.exists(manifest_key):
        raise HTTPException(
            status_code=400,
            detail="HLS manifest missing on disk; run scripts/transcode-hls.sh for this asset first",
        )
    asset.hls_url = f"{_base_url(settings)}/media/{asset_id}/hls/{HLS_MANIFEST}"
    await session.commit()
    return to_staff(asset, settings)


async def hls_path(storage: StoragePort, asset_id: str, file: str) -> Path:
    if not HLS_FILE_PATTERN.match(file) or ".." in file:
        raise HTTPException(status_code=400, detail="Invalid HLS file name")
    content_type = HLS_CONTENT_TYPES.get(Path(file).suffix.lower())
    if content_type is None:
        raise HTTPException(status_code=400, detail="Unsupported HLS file type")
    key = f"hls/{asset_id}/{file}"
    if not await storage.exists(key):
        raise HTTPException(status_code=404, detail="HLS file not found")
    return await storage.get_path(key)
