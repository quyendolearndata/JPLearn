"""HTTP router for playback sessions, heartbeat checkpoints, and resume tracking (UC-L16, UC-L17)."""

from __future__ import annotations

from datetime import timedelta, timezone
from jplearn_api.settings import Settings
from jplearn_api.entrypoints.http.dependencies import get_app_settings
from fastapi import APIRouter, Depends, Header, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    EndPlaybackCommand,
    SendCheckpointCommand,
    StartPlaybackCommand,
)
from jplearn_api.application.handlers.playback import (
    handle_end_playback,
    handle_get_item_resume,
    handle_get_playback,
    handle_list_resume,
    handle_send_checkpoint,
    handle_start_playback,
)
from jplearn_api.application.queries import (
    GetItemResumeQuery,
    GetPlaybackQuery,
    ListResumeQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.domain.playback import PlaybackStatus
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session, require_capability
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.schemas import (
    CheckpointAckPublic,
    CheckpointBody,
    EndPlaybackBody,
    PlaybackCreatedPublic,
    PlaybackStatusPublic,
    ResumeItemPublic,
    ResumeListPublic,
    StartPlaybackBody,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(tags=["Playback"])


@router.post(
    "/playbacks",
    response_model=PlaybackCreatedPublic,
    operation_id="startPlayback",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001", "FR-RSM-001"]},
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Playback session successfully started or taken over",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlaybackCreatedPublic"}
                }
            },
        },
        400: {"description": "Invalid input"},
        401: {"description": "Authentication required"},
        404: {"description": "Catalog item not found or unpublished"},
        409: {"description": "Playback lease conflict on another device"},
    },
)
async def start_playback(
    payload: StartPlaybackBody,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    _cap: None = Depends(require_capability("playback_tracking_enabled")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=200),
) -> PlaybackCreatedPublic:
    uow = create_uow(session)
    cmd = StartPlaybackCommand(
        user_id=user.id,
        catalog_item_id=payload.catalog_item_id,
        device_id=payload.device_id,
        device_info=payload.device_info,
        take_over=payload.take_over,
        idempotency_key=idempotency_key,
        content_version_id=payload.content_version_id,
    )
    try:
        playback_session, resume_cp = await handle_start_playback(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    resume_public = None
    if resume_cp is not None:
        resume_public = ResumeItemPublic(
            catalog_item_id=resume_cp.catalog_item_id,
            playback_id=None,
            position_ms=resume_cp.position_ms,
            duration_ms=0,
            scene_id=None,
            updated_at=resume_cp.updated_at,
        )

    last_time = playback_session.last_server_time if playback_session.last_server_time.tzinfo else playback_session.last_server_time.replace(tzinfo=timezone.utc)
    lease_expires = last_time + timedelta(seconds=45)

    return PlaybackCreatedPublic(
        playback_id=playback_session.id,
        catalog_item_id=playback_session.catalog_item_id,
        epoch=playback_session.epoch,
        lease_expires_at=lease_expires,
        initial_position_ms=playback_session.last_position_ms,
        resume_checkpoint=resume_public,
    )


@router.get(
    "/playbacks/{id}",
    response_model=PlaybackStatusPublic,
    operation_id="getPlayback",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001"]},
    responses={
        200: {
            "description": "Playback session details and lease status",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlaybackStatusPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
        404: {"description": "Playback session not found"},
    },
)
async def get_playback(
    id: UUIDPath,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> PlaybackStatusPublic:
    uow = create_uow(session)
    query = GetPlaybackQuery(user_id=user.id, playback_id=id)
    try:
        playback_session = await handle_get_playback(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    last_time = playback_session.last_server_time if playback_session.last_server_time.tzinfo else playback_session.last_server_time.replace(tzinfo=timezone.utc)
    lease_expires = last_time + timedelta(seconds=45)

    return PlaybackStatusPublic(
        playback_id=playback_session.id,
        catalog_item_id=playback_session.catalog_item_id,
        device_id=playback_session.client_instance_id,
        status=playback_session.status.value,
        epoch=playback_session.epoch,
        lease_expires_at=lease_expires if playback_session.status == PlaybackStatus.ACTIVE else None,
        last_seq=playback_session.last_seq,
        last_position_ms=playback_session.last_position_ms,
        duration_ms=0,
        cumulative_active_ms=playback_session.last_client_cumulative_ms,
        server_acknowledged_active_ms=playback_session.total_active_ms,
        created_at=playback_session.created_at,
        updated_at=playback_session.updated_at,
        closed_at=playback_session.closed_at,
    )



@router.put(
    "/playbacks/{id}/checkpoints/{seq}",
    response_model=CheckpointAckPublic,
    operation_id="sendPlaybackCheckpoint",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001", "FR-RSM-001"]},
    responses={
        200: {
            "description": "Checkpoint recorded and active watch time credited",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/CheckpointAckPublic"}
                }
            },
        },
        400: {"description": "Invalid checkpoint values"},
        401: {"description": "Authentication required"},
        404: {"description": "Playback session not found"},
        409: {"description": "Sequence mismatch, duplicate conflict, or session superseded"},
    },
)
async def send_playback_checkpoint(
    id: UUIDPath,
    seq: int = Path(ge=1, description="Strictly consecutive checkpoint sequence number"),
    payload: CheckpointBody = ...,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> CheckpointAckPublic:
    uow = create_uow(session)
    cmd = SendCheckpointCommand(
        user_id=user.id,
        playback_id=id,
        seq=seq,
        position_ms=payload.position_ms,
        duration_ms=payload.duration_ms,
        playback_rate=payload.playback_rate,
        state=payload.state,
        client_cumulative_active_ms=payload.client_cumulative_active_ms,
        client_epoch=payload.client_epoch,
        scene_id=payload.scene_id,
    )
    try:
        receipt, playback_session = await handle_send_checkpoint(cmd, uow, credit_enabled=settings.playback_tracking_enabled)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    last_time = playback_session.last_server_time if playback_session.last_server_time.tzinfo else playback_session.last_server_time.replace(tzinfo=timezone.utc)
    lease_expires = last_time + timedelta(seconds=45)

    return CheckpointAckPublic(
        seq=receipt.seq,
        accepted_delta_ms=receipt.accepted_delta_ms,
        server_acknowledged_active_ms=receipt.cumulative_active_ms,
        lease_expires_at=lease_expires,
        epoch=playback_session.epoch,
    )


@router.post(
    "/playbacks/{id}/end",
    response_model=PlaybackStatusPublic,
    operation_id="endPlayback",
    openapi_extra={"x-jplearn-fr": ["FR-WAT-001", "FR-RSM-001"]},
    responses={
        200: {
            "description": "Playback session successfully ended and lease released",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlaybackStatusPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
        404: {"description": "Playback session not found"},
    },
)
async def end_playback(
    id: UUIDPath,
    payload: EndPlaybackBody,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_app_settings),
) -> PlaybackStatusPublic:
    uow = create_uow(session)
    cmd = EndPlaybackCommand(
        user_id=user.id,
        playback_id=id,
        final_seq=payload.final_seq,
        final_position_ms=payload.final_position_ms,
        final_duration_ms=payload.final_duration_ms,
        final_playback_rate=payload.final_playback_rate,
        final_client_cumulative_active_ms=payload.final_client_cumulative_active_ms,
        final_client_epoch=payload.final_client_epoch,
        final_scene_id=payload.final_scene_id,
    )
    try:
        playback_session = await handle_end_playback(cmd, uow, credit_enabled=settings.playback_tracking_enabled)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return PlaybackStatusPublic(
        playback_id=playback_session.id,
        catalog_item_id=playback_session.catalog_item_id,
        device_id=playback_session.client_instance_id,
        status=playback_session.status.value,
        epoch=playback_session.epoch,
        lease_expires_at=None,
        last_seq=playback_session.last_seq,
        last_position_ms=playback_session.last_position_ms,
        duration_ms=0,
        cumulative_active_ms=playback_session.last_client_cumulative_ms,
        server_acknowledged_active_ms=playback_session.total_active_ms,
        created_at=playback_session.created_at,
        updated_at=playback_session.updated_at,
        closed_at=playback_session.closed_at,
    )


@router.get(
    "/me/resume",
    response_model=ResumeListPublic,
    operation_id="listResume",
    openapi_extra={"x-jplearn-fr": ["FR-RSM-001"]},
    responses={
        200: {
            "description": "List of resume checkpoints sorted by recent activity",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ResumeListPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
    },
)
async def list_resume(
    offset: int = Query(ge=0, default=0),
    limit: int = Query(ge=1, le=100, default=50),
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> ResumeListPublic:
    uow = create_uow(session)
    query = ListResumeQuery(user_id=user.id, offset=offset, limit=limit)
    try:
        items, total = await handle_list_resume(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return ResumeListPublic(
        items=[
            ResumeItemPublic(
                catalog_item_id=item.catalog_item_id,
                playback_id=None,
                position_ms=item.position_ms,
                duration_ms=0,
                scene_id=None,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/me/resume/{catalog_item_id}",
    response_model=ResumeItemPublic,
    operation_id="getResumeCheckpoint",
    openapi_extra={"x-jplearn-fr": ["FR-RSM-001"]},
    responses={
        200: {
            "description": "Resume checkpoint for the specified catalog item",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ResumeItemPublic"}
                }
            },
        },
        401: {"description": "Authentication required"},
        404: {"description": "No resume checkpoint found for this item"},
    },
)
async def get_resume_checkpoint(
    catalog_item_id: UUIDPath,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> ResumeItemPublic:
    uow = create_uow(session)
    query = GetItemResumeQuery(user_id=user.id, catalog_item_id=catalog_item_id)
    try:
        cp = await handle_get_item_resume(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return ResumeItemPublic(
        catalog_item_id=cp.catalog_item_id,
        playback_id=None,
        position_ms=cp.position_ms,
        duration_ms=0,
        scene_id=None,
        updated_at=cp.updated_at,
    )
