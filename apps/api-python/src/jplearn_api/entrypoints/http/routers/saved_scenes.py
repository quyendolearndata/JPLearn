"""HTTP router for learner saved scenes (bookmarks)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import DeleteSavedSceneCommand, SaveSceneCommand
from jplearn_api.application.handlers.saved_scenes import (
    handle_delete_saved_scene,
    handle_list_saved_scenes,
    handle_save_scene,
)
from jplearn_api.application.queries import ListSavedScenesQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session, require_capability
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.schemas import SavedSceneItemPublic, SavedScenePublic
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(tags=["Library"])


@router.put(
    "/me/saved-scenes/{scene_id}",
    response_model=SavedScenePublic,
    operation_id="saveScene",
    openapi_extra={"x-jplearn-fr": ["FR-BMK-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Scene was already saved (idempotent)"},
        201: {
            "description": "Scene successfully saved",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SavedScenePublic"}}},
        },
        400: {"description": "Scene not in published current version"},
        401: {"description": "Authentication required"},
        404: {"description": "Scene not found"},
    },
)
async def save_scene(
    scene_id: UUIDPath,
    response: Response,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
    _cap: None = Depends(require_capability("video_scene_breakdown_enabled")),
) -> SavedScenePublic:
    uow = create_uow(session)
    try:
        saved, created = await handle_save_scene(
            SaveSceneCommand(user_id=user.id, scene_id=scene_id),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    if created:
        response.status_code = status.HTTP_201_CREATED

    return SavedScenePublic(
        id=saved.id,
        scene_id=saved.scene_id,
        saved_at=saved.saved_at,
    )


@router.get(
    "/me/saved-scenes",
    response_model=list[SavedSceneItemPublic],
    operation_id="listSavedScenes",
    openapi_extra={"x-jplearn-fr": ["FR-BMK-001", "FR-LRN-001"]},
    responses={
        200: {"description": "List of saved scenes with availability projection"},
        401: {"description": "Authentication required"},
    },
)
async def list_saved_scenes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> list[SavedSceneItemPublic]:
    uow = create_uow(session)
    try:
        projections, _total = await handle_list_saved_scenes(
            ListSavedScenesQuery(user_id=user.id, offset=offset, limit=limit),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return [
        SavedSceneItemPublic(
            id=p.id,
            scene_id=p.scene_id,
            saved_at=p.saved_at,
            availability=p.availability,  # type: ignore[arg-type]
            unavailable_reason=p.unavailable_reason,
            catalog_item_id=p.catalog_item_id,
            content_version_id=p.content_version_id,
            scene_index=p.scene_index,
            start_time_seconds=p.start_time_seconds,
            end_time_seconds=p.end_time_seconds,
            title_jp=p.title_jp,
            transcript_jp=p.transcript_jp,
        )
        for p in projections
    ]


@router.delete(
    "/me/saved-scenes/{scene_id}",
    operation_id="deleteSavedScene",
    openapi_extra={"x-jplearn-fr": ["FR-BMK-001", "FR-LRN-001"]},
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Saved scene deleted idempotently"},
        401: {"description": "Authentication required"},
    },
)
async def delete_saved_scene(
    scene_id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> Response:
    uow = create_uow(session)
    try:
        await handle_delete_saved_scene(
            DeleteSavedSceneCommand(user_id=user.id, scene_id=scene_id),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
