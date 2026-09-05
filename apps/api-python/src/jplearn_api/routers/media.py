from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path as FastPath, Query, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.handlers.media import (
    COMMIT_CANCELLATION_GRACE_SECONDS,
    handle_get_media,
    handle_register_hls,
    handle_stream_hls,
    handle_stream_media,
    handle_upload_media,
)
from jplearn_api.application.ports.unit_of_work import UnitOfWorkFactory
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_media_repository, create_uow
from jplearn_api.deps import UUIDPath, get_media_signer, get_session, get_storage, get_uow_factory
from jplearn_api.domain.errors import DomainError
from jplearn_api.domain.range_parser import RangeNotSatisfiableError
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.roles import require_roles
from jplearn_api.schemas import MediaAssetStaff
from jplearn_api.security import require_media_access
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
    storage: StoragePort = Depends(get_storage),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    _user: UserDTO = Depends(require_roles("teacher", "admin")),
) -> MediaAssetStaff:
    signer = get_media_signer(request)

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
        dto = await handle_upload_media(
            catalog_item_id=id,
            first_chunk=first_chunk,
            stream=stream_rest(),
            filename=filename,
            content_type=content_type,
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
            _grace_seconds=COMMIT_CANCELLATION_GRACE_SECONDS,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return MediaAssetStaff(**asdict(dto))


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
    _user: UserDTO = Depends(require_roles("teacher", "admin")),
) -> MediaAssetStaff:
    uow = create_uow(session)
    signer = get_media_signer(request)

    try:
        dto = await handle_register_hls(
            asset_id=id,
            uow=uow,
            storage=storage,
            signer=signer,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return MediaAssetStaff(**asdict(dto))


@router.get(
    "/media/{id}",
    response_class=Response,
    operation_id="streamMedia",
    tags=["Media"],
    openapi_extra={
        "x-jplearn-fr": ["FR-CMS-003", "FR-CMS-004"],
        "security": [{"bearerAuth": []}, {"signedQuery": []}],
    },
    responses={
        200: {
            "description": "Media stream",
            "content": {
                "video/mp4": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        401: {"description": "Missing or invalid JWT/signature"},
        404: {"description": "Asset not found"},
    },
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
    media_repo = create_media_repository(session)
    range_header = request.headers.get("range")
    try:
        stream_dto = await handle_stream_media(
            asset_id=id,
            media_repo=media_repo,
            storage=storage,
            range_header=range_header,
        )
    except RangeNotSatisfiableError as exc:
        raise HTTPException(
            status_code=416,
            detail="Range Not Satisfiable",
            headers={
                "Content-Range": f"bytes */{exc.total_size}",
                "Accept-Ranges": "bytes",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    if stream_dto.range is not None:
        status_code = 206
        headers = {
            "Content-Range": f"bytes {stream_dto.range.start}-{stream_dto.range.end}/{stream_dto.range.total_size}",
            "Content-Length": str(stream_dto.range.length),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }
    else:
        status_code = 200
        headers = {
            "Content-Length": str(stream_dto.total_size),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }

    return StreamingResponse(
        stream_dto.content_stream,
        status_code=status_code,
        media_type=stream_dto.content_type,
        headers=headers,
    )


@router.get(
    "/media/{id}/hls/{file:path}",
    response_class=Response,
    operation_id="streamHls",
    tags=["Media"],
    openapi_extra={
        "x-jplearn-fr": ["NFR-PERF-002"],
        "security": [{"bearerAuth": []}, {"signedQuery": []}],
    },
    responses={
        200: {
            "content": {
                "application/vnd.apple.mpegurl": {},
                "video/mp2t": {},
                "video/iso.segment": {},
            }
        },
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
    media_repo = create_media_repository(session)
    try:
        await handle_get_media(id, media_repo)
    except DomainError as exc:
        http_exc = map_domain_error_to_http(exc)
        raise HTTPException(
            status_code=http_exc.status_code,
            detail=http_exc.detail,
            headers={"X-Content-Type-Options": "nosniff"},
        ) from exc

    range_header = request.headers.get("range")
    try:
        stream_dto = await handle_stream_hls(
            storage=storage,
            asset_id=id,
            file=file,
            range_header=range_header,
        )
    except RangeNotSatisfiableError as exc:
        raise HTTPException(
            status_code=416,
            detail="Range Not Satisfiable",
            headers={
                "Content-Range": f"bytes */{exc.total_size}",
                "Accept-Ranges": "bytes",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except DomainError as exc:
        http_exc = map_domain_error_to_http(exc)
        raise HTTPException(
            status_code=http_exc.status_code,
            detail=http_exc.detail,
            headers={"X-Content-Type-Options": "nosniff"},
        ) from exc

    is_manifest = file.endswith(".m3u8")
    if is_manifest and exp and sig:
        chunks = []
        async for chunk in stream_dto.content_stream:
            chunks.append(chunk)
        manifest = b"".join(chunks).decode("utf-8")
        lines = []
        for line in manifest.split("\n"):
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("#"):
                lines.append(line)
            else:
                lines.append(f"{trimmed}?exp={quote(str(exp))}&sig={quote(sig)}")
        return PlainTextResponse(
            "\n".join(lines),
            media_type=stream_dto.content_type,
            headers={
                "Accept-Ranges": "none",
                "X-Content-Type-Options": "nosniff",
            },
        )

    if stream_dto.range is not None:
        status_code = 206
        headers = {
            "Content-Range": f"bytes {stream_dto.range.start}-{stream_dto.range.end}/{stream_dto.range.total_size}",
            "Content-Length": str(stream_dto.range.length),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }
    else:
        status_code = 200
        headers = {
            "Content-Length": str(stream_dto.total_size),
            "Accept-Ranges": "bytes" if not is_manifest else "none",
            "X-Content-Type-Options": "nosniff",
        }

    return StreamingResponse(
        stream_dto.content_stream,
        status_code=status_code,
        media_type=stream_dto.content_type,
        headers=headers,
    )
