from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path as FastPath, Query, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api import media_service
from jplearn_api.deps import UUIDPath, get_session, get_storage
from jplearn_api.media_access import require_media_access
from jplearn_api.models import User
from jplearn_api.roles import require_roles
from jplearn_api.schemas import MediaAssetStaff
from jplearn_api.storage import StoragePort

router = APIRouter()


@router.post(
    "/staff/catalog/{id}/media",
    status_code=201,
    response_model=MediaAssetStaff,
    operation_id="uploadMedia",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-001"]},
)
async def upload_media(
    id: UUIDPath,
    request: Request,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    storage: StoragePort = Depends(get_storage),
    _user: User = Depends(require_roles("teacher", "admin")),
) -> MediaAssetStaff:
    return await media_service.upload(session, request.app.state.settings, storage, id, file)


@router.post(
    "/staff/media/{id}/hls",
    status_code=201,
    response_model=MediaAssetStaff,
    operation_id="registerHls",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-001", "NFR-PERF-002"]},
    responses={
        400: {"description": "HLS manifest missing on disk"},
        403: {"description": "Not teacher or admin"},
    },
)
async def register_hls(
    id: UUIDPath,
    request: Request,
    session: AsyncSession = Depends(get_session),
    storage: StoragePort = Depends(get_storage),
    _user: User = Depends(require_roles("teacher", "admin")),
) -> MediaAssetStaff:
    return await media_service.register_hls(session, request.app.state.settings, storage, id)


@router.get(
    "/media/{id}",
    operation_id="streamMedia",
    tags=["Media"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-003", "FR-CMS-004"]},
    responses={401: {"description": "Missing or invalid JWT/signature"}, 404: {"description": "Asset not found"}},
)
async def stream_media(
    id: UUIDPath,
    request: Request,
    exp: int | None = Query(default=None, description="Unix seconds expiry (required if no Bearer)"),
    sig: str | None = Query(default=None, pattern="^[a-f0-9]{64}$"),
    session: AsyncSession = Depends(get_session),
    storage: StoragePort = Depends(get_storage),
    _access: None = Depends(require_media_access),
) -> Response:
    stream_iter, size, mime = await media_service.stream(session, storage, id)
    return StreamingResponse(
        stream_iter,
        media_type=mime,
        headers={
            "Content-Length": str(size),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/media/{id}/hls/{file:path}",
    operation_id="streamHls",
    tags=["Media"],
    openapi_extra={"x-jplearn-fr": ["NFR-PERF-002"]},
    responses={
        400: {"description": "Invalid or unsupported file name"},
        401: {"description": "Missing or invalid JWT/signature"},
        404: {"description": "Asset or HLS file not found"},
    },
)
async def stream_hls(
    id: UUIDPath,
    request: Request,
    file: str = FastPath(..., pattern=r"^[A-Za-z0-9._-]+$"),
    exp: int | None = Query(default=None, description="Unix seconds expiry (required if no Bearer)"),
    sig: str | None = Query(default=None, pattern="^[a-f0-9]{64}$"),
    session: AsyncSession = Depends(get_session),
    storage: StoragePort = Depends(get_storage),
    _access: None = Depends(require_media_access),
) -> Response:
    await media_service.get(session, id)
    try:
        stream_iter, size, content_type = await media_service.stream_hls(storage, id, file)
    except HTTPException as exc:
        # Nest sets @Header("X-Content-Type-Options", "nosniff") on every
        # response of this handler, including 400/404 errors.
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={"X-Content-Type-Options": "nosniff"},
        ) from exc

    headers = {"X-Content-Type-Options": "nosniff"}
    if file.endswith(".m3u8") and exp and sig:
        chunks = []
        async for chunk in stream_iter:
            chunks.append(chunk)
        manifest = b"".join(chunks).decode("utf-8")
        lines = []
        for line in manifest.split("\n"):
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("#"):
                lines.append(line)
            else:
                lines.append(f"{trimmed}?exp={quote(str(exp))}&sig={quote(sig)}")
        return PlainTextResponse("\n".join(lines), media_type=content_type, headers=headers)

    return StreamingResponse(
        stream_iter,
        media_type=content_type,
        headers={
            "Content-Length": str(size),
            "X-Content-Type-Options": "nosniff",
        },
    )
