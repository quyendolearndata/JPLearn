from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import ReturnToDraftCommand, SceneInput, UpdateContentDraftCommand
from jplearn_api.application.handlers.content import (
    handle_get_published_content,
    handle_get_staff_content,
    handle_return_to_draft,
    handle_update_content_draft,
)
from jplearn_api.application.queries import GetPublishedContentQuery, GetStaffContentQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session, require_capability
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    CatalogItemStaff,
    ContentUpdateBody,
    ContentVersionPublic,
    ContentVersionStaff,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(tags=["Catalog"])


@router.get(
    "/catalog/{id}/content",
    response_model=ContentVersionPublic,
    operation_id="getCatalogItemContent",
    openapi_extra={"x-jplearn-fr": ["FR-SCN-001", "FR-LRN-001"]},
    responses={
        404: {"description": "Catalog item not found or unpublished"},
    },
)
async def get_catalog_content(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_user),
    _cap: None = Depends(require_capability("video_scene_breakdown_enabled")),
) -> ContentVersionPublic:
    uow = create_uow(session)
    query = GetPublishedContentQuery(catalog_item_id=id)
    try:
        version_dto = await handle_get_published_content(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return ContentVersionPublic.model_validate(version_dto)


@router.get(
    "/staff/catalog/{id}/content",
    response_model=ContentVersionStaff,
    operation_id="getStaffCatalogItemContent",
    openapi_extra={"x-jplearn-fr": ["FR-SCN-001"]},
    responses={
        403: {"description": "Staff only or capability disabled"},
        404: {"description": "Catalog item not found"},
    },
)
async def get_staff_catalog_content(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
    _cap: None = Depends(require_capability("video_scene_breakdown_enabled")),
) -> ContentVersionStaff:
    uow = create_uow(session)
    query = GetStaffContentQuery(catalog_item_id=id)
    try:
        version_dto = await handle_get_staff_content(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return ContentVersionStaff.model_validate(version_dto)


@router.put(
    "/staff/catalog/{id}/content",
    response_model=ContentVersionStaff,
    operation_id="putStaffCatalogItemContent",
    openapi_extra={"x-jplearn-fr": ["FR-SCN-001"]},
    responses={
        400: {"description": "Invalid scene timing or non-draft item"},
        403: {"description": "Staff only or capability disabled"},
        404: {"description": "Catalog item not found"},
        409: {"description": "Revision conflict"},
    },
)
async def update_staff_catalog_content(
    id: UUIDPath,
    body: ContentUpdateBody,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
    _cap: None = Depends(require_capability("video_scene_breakdown_enabled")),
) -> ContentVersionStaff:
    uow = create_uow(session)
    cmd = UpdateContentDraftCommand(
        catalog_item_id=id,
        version_revision=body.version_revision,
        scenes=[
            SceneInput(
                scene_index=s.scene_index,
                start_time_seconds=s.start_time_seconds,
                end_time_seconds=s.end_time_seconds,
                title_jp=s.title_jp,
                transcript_jp=s.transcript_jp,
            )
            for s in body.scenes
        ],
    )
    try:
        version_dto = await handle_update_content_draft(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return ContentVersionStaff.model_validate(version_dto)


@router.post(
    "/staff/catalog/{id}/return-to-draft",
    response_model=CatalogItemStaff,
    operation_id="returnCatalogItemToDraft",
    openapi_extra={"x-jplearn-fr": ["FR-SCN-001", "FR-CMS-002"]},
    responses={
        400: {"description": "Item is not in level_qa status"},
        403: {"description": "Staff only or capability disabled"},
        404: {"description": "Catalog item not found"},
    },
)
async def return_catalog_item_to_draft(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
    _cap: None = Depends(require_capability("video_scene_breakdown_enabled")),
) -> CatalogItemStaff:
    uow = create_uow(session)
    cmd = ReturnToDraftCommand(catalog_item_id=id)
    try:
        item_dto = await handle_return_to_draft(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return CatalogItemStaff.model_validate(item_dto)
