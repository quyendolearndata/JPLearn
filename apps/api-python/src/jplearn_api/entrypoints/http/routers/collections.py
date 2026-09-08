"""HTTP router for personal collections (UC-L23)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    CreateCollectionCommand,
    DeleteCollectionCommand,
    PatchCollectionCommand,
    UpdateCollectionScenesCommand,
)
from jplearn_api.application.handlers.collections import (
    handle_create_collection,
    handle_delete_collection,
    handle_get_collection,
    handle_list_collections,
    handle_patch_collection,
    handle_update_collection_scenes,
)
from jplearn_api.application.queries import GetCollectionQuery, ListCollectionsQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session, require_capability
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.schemas import (
    CollectionDetailPublic,
    CollectionPublic,
    CollectionSceneItemPublic,
    CreateCollectionBody,
    PatchCollectionBody,
    UpdateCollectionScenesBody,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(tags=["Library"], dependencies=[Depends(require_capability("personal_collections_enabled"))])


@router.post(
    "/me/collections",
    response_model=CollectionPublic,
    operation_id="createCollection",
    openapi_extra={"x-jplearn-fr": ["FR-COL-001", "FR-LRN-001"]},
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "description": "Collection was already created (idempotent replay)",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/CollectionPublic"}
                }
            },
        },
        201: {
            "description": "Collection successfully created",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/CollectionPublic"}
                }
            },
        },
        400: {"description": "Invalid input or collection quota exceeded"},
        401: {"description": "Authentication required"},
        409: {"description": "Idempotency key reused with different payload"},
    },
)
async def create_collection(
    body: CreateCollectionBody,
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        max_length=128,
        description="Optional idempotency key for safely retrying collection creation.",
    ),
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> CollectionPublic:
    uow = create_uow(session)
    try:
        coll, created = await handle_create_collection(
            CreateCollectionCommand(
                user_id=user.id,
                name=body.name,
                idempotency_key=idempotency_key,
            ),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    if not created:
        response.status_code = status.HTTP_200_OK

    return CollectionPublic(
        id=coll.id,
        name=coll.name,
        revision=coll.revision,
        scene_count=coll.scene_count,
        created_at=coll.created_at,
        updated_at=coll.updated_at,
    )


@router.get(
    "/me/collections",
    response_model=list[CollectionPublic],
    operation_id="listCollections",
    openapi_extra={"x-jplearn-fr": ["FR-COL-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "List of learner collections"},
        401: {"description": "Authentication required"},
    },
)
async def list_collections(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> list[CollectionPublic]:
    uow = create_uow(session)
    try:
        collections, _total = await handle_list_collections(
            ListCollectionsQuery(
                user_id=user.id,
                offset=offset,
                limit=limit,
                cursor=cursor,
            ),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return [
        CollectionPublic(
            id=c.id,
            name=c.name,
            revision=c.revision,
            scene_count=c.scene_count,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in collections
    ]


@router.get(
    "/me/collections/{collection_id}",
    response_model=CollectionDetailPublic,
    operation_id="getCollection",
    openapi_extra={"x-jplearn-fr": ["FR-COL-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Collection details including scenes and availability"},
        401: {"description": "Authentication required"},
        404: {"description": "Collection not found"},
    },
)
async def get_collection(
    collection_id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> CollectionDetailPublic:
    uow = create_uow(session)
    try:
        detail = await handle_get_collection(
            GetCollectionQuery(user_id=user.id, collection_id=collection_id),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CollectionDetailPublic(
        id=detail.id,
        name=detail.name,
        revision=detail.revision,
        scene_count=detail.scene_count,
        created_at=detail.created_at,
        updated_at=detail.updated_at,
        scenes=[
            CollectionSceneItemPublic(
                position=s.position,
                scene_id=s.scene_id,
                availability=s.availability.value,
                unavailable_reason=s.reason,
                catalog_item_id=s.scene["catalog_item_id"] if s.scene else None,
                content_version_id=s.scene["content_version_id"] if s.scene else None,
                scene_index=s.scene["scene_index"] if s.scene else None,
                start_time_seconds=s.scene["start_time_seconds"] if s.scene else None,
                end_time_seconds=s.scene["end_time_seconds"] if s.scene else None,
                title_jp=s.scene["title_jp"] if s.scene else None,
                transcript_jp=s.scene["transcript_jp"] if s.scene else None,
                added_at=s.added_at,
            )
            for s in detail.scenes
        ],
    )


@router.patch(
    "/me/collections/{collection_id}",
    response_model=CollectionPublic,
    operation_id="patchCollection",
    openapi_extra={"x-jplearn-fr": ["FR-COL-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Collection name successfully updated"},
        400: {"description": "Invalid collection name"},
        401: {"description": "Authentication required"},
        404: {"description": "Collection not found"},
        409: {"description": "Revision conflict"},
    },
)
async def patch_collection(
    collection_id: UUIDPath,
    body: PatchCollectionBody,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> CollectionPublic:
    uow = create_uow(session)
    try:
        updated = await handle_patch_collection(
            PatchCollectionCommand(
                user_id=user.id,
                collection_id=collection_id,
                expected_revision=body.expected_revision,
                name=body.name,
            ),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CollectionPublic(
        id=updated.id,
        name=updated.name,
        revision=updated.revision,
        scene_count=updated.scene_count,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.put(
    "/me/collections/{collection_id}/scenes",
    response_model=CollectionPublic,
    operation_id="updateCollectionScenes",
    openapi_extra={"x-jplearn-fr": ["FR-COL-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Collection scenes successfully replaced"},
        400: {"description": "Invalid scene list or scene not saved"},
        401: {"description": "Authentication required"},
        404: {"description": "Collection not found"},
        409: {"description": "Revision conflict"},
    },
)
async def update_collection_scenes(
    collection_id: UUIDPath,
    body: UpdateCollectionScenesBody,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> CollectionPublic:
    uow = create_uow(session)
    try:
        updated = await handle_update_collection_scenes(
            UpdateCollectionScenesCommand(
                user_id=user.id,
                collection_id=collection_id,
                expected_revision=body.expected_revision,
                scene_ids=body.scene_ids,
            ),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CollectionPublic(
        id=updated.id,
        name=updated.name,
        revision=updated.revision,
        scene_count=updated.scene_count,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete(
    "/me/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteCollection",
    openapi_extra={"x-jplearn-fr": ["FR-COL-001", "FR-LRN-001"]},
    responses={
        204: {"description": "Collection deleted idempotently"},
        401: {"description": "Authentication required"},
    },
)
async def delete_collection(
    collection_id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> Response:
    uow = create_uow(session)
    try:
        await handle_delete_collection(
            DeleteCollectionCommand(
                user_id=user.id,
                collection_id=collection_id,
            ),
            uow=uow,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
