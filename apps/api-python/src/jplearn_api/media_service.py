from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
import re
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

    # 1. Validate file extension and MIME per ADR-005 BA decision
    filename = (file.filename or "").lower().strip()
    if not filename.endswith(".mp4"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension: expected '.mp4', got '{Path(filename).suffix}'",
        )
    if file.content_type != "video/mp4":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid MIME type: expected 'video/mp4', got '{file.content_type}'",
        )

    # 2. Inspect first chunk for MP4 magic bytes (ftyp box at offset 4)
    first_chunk = await file.read(64 * 1024)
    if not first_chunk or len(first_chunk) < 8:
        raise HTTPException(status_code=400, detail="File must not be empty and must contain a valid header")
    if first_chunk[4:8] != b"ftyp":
        raise HTTPException(status_code=400, detail="Invalid MP4 file signature: expected 'ftyp' box")

    asset_id = str(uuid4())
    temp_key = f"{asset_id}.part"
    final_key = f"{asset_id}.bin"

    async def file_stream() -> AsyncIterator[bytes]:
        yield first_chunk
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    # 3. Stream to staging key and promote
    try:
        await storage.stage_stream(temp_key, file_stream())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        await storage.promote(temp_key, final_key)
    except Exception as exc:
        await storage.delete(temp_key)
        raise HTTPException(status_code=500, detail="Failed to store media file") from exc

    # 4. Insert DB record with rollback and compensation deletion
    asset = MediaAsset(
        id=asset_id,
        catalog_item_id=catalog_item_id,
        storage_key=final_key,
        playback_url=f"{_base_url(settings)}/media/{asset_id}",
        hls_url=None,
        mime="video/mp4",
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


class RangeNotSatisfiable(Exception):
    def __init__(self, total_size: int) -> None:
        self.total_size = total_size


def parse_byte_range(range_header: str | None, total_size: int) -> tuple[int, int, int] | None:
    """Parse HTTP Range header for single byte range per RFC 7233 / RFC 9110.

    Returns (start, end, length) if a valid satisfiable single range is requested.
    Returns None if Range header is missing, or contains multiple ranges / unsupported units (falls back to 200).
    Raises RangeNotSatisfiable if range is unsatisfiable (HTTP 416).
    """
    if not range_header or not range_header.strip():
        return None

    range_header = range_header.strip()
    if not range_header.startswith("bytes="):
        # Ignore unsupported range unit per RFC 7233 §3.1
        return None

    specs = range_header[len("bytes=") :].strip()
    # RFC 7233 §3.1: server supporting range requests MAY ignore multiple ranges and serve full 200 response
    if "," in specs:
        return None

    if total_size <= 0:
        raise RangeNotSatisfiable(total_size)

    if specs.startswith("-"):
        # Suffix range: bytes=-suffix
        suffix_str = specs[1:].strip()
        if not suffix_str.isdigit():
            return None
        suffix = int(suffix_str)
        if suffix <= 0:
            raise RangeNotSatisfiable(total_size)
        if suffix >= total_size:
            start = 0
        else:
            start = total_size - suffix
        end = total_size - 1
        return (start, end, end - start + 1)

    if "-" not in specs:
        return None

    start_str, end_str = specs.split("-", 1)
    start_str = start_str.strip()
    end_str = end_str.strip()

    if not start_str.isdigit():
        return None

    start = int(start_str)
    if start >= total_size:
        raise RangeNotSatisfiable(total_size)

    if not end_str:
        # Open-ended: bytes=start-
        end = total_size - 1
    else:
        if not end_str.isdigit():
            return None
        end = int(end_str)
        if start > end:
            raise RangeNotSatisfiable(total_size)
        if end >= total_size:
            end = total_size - 1

    return (start, end, end - start + 1)


async def stream(
    session: AsyncSession,
    storage: StoragePort,
    asset_id: str,
    range_header: str | None = None,
) -> tuple[AsyncIterator[bytes], int, str, int, dict[str, str]]:
    """Retrieve async byte stream, total size, MIME, status_code, and range response headers."""
    asset = await get(session, asset_id)
    if not await storage.exists(asset.storage_key):
        raise HTTPException(status_code=404, detail="Media asset not found")
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


async def stream_hls(
    storage: StoragePort,
    asset_id: str,
    file: str,
    range_header: str | None = None,
) -> tuple[AsyncIterator[bytes], int, str, int, dict[str, str]]:
    """Retrieve async stream for HLS manifest or segment without leaking storage paths."""
    if not HLS_FILE_PATTERN.match(file) or ".." in file or "/" in file or "\\" in file:
        raise HTTPException(status_code=400, detail="Invalid HLS file name")
    suffix = Path(file).suffix.lower()
    content_type = HLS_CONTENT_TYPES.get(suffix)
    if content_type is None:
        raise HTTPException(status_code=400, detail="Unsupported HLS file type")
    key = f"hls/{asset_id}/{file}"
    if not await storage.exists(key):
        raise HTTPException(status_code=404, detail="HLS file not found")
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
