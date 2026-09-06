from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    CreateCatalogItemCommand,
    PublishCatalogItemCommand,
    SubmitCatalogForQaCommand,
    UnpublishCatalogItemCommand,
    UpdateDraftCatalogItemCommand,
)
from jplearn_api.application.handlers.catalog import (
    handle_create_catalog_item,
    handle_get_staff_catalog_item,
    handle_list_published,
    handle_list_staff_catalog,
    handle_publish,
    handle_submit_qa,
    handle_unpublish,
    handle_update_draft_catalog_item,
)
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.queries import (
    GetStaffCatalogItemQuery,
    ListPublishedCatalogQuery,
    ListStaffCatalogQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_catalog_query, create_catalog_repository, create_uow
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session, get_storage
from jplearn_api.domain.errors import DomainError, EntityNotFoundError
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    CatalogItemPatch,
    CatalogItemPublic,
    CatalogItemStaff,
    CatalogItemWrite,
    CatalogList,
    CatalogStaffList,
)
from jplearn_api.entrypoints.http.security import require_user
from fastapi import HTTPException

router = APIRouter()


@router.get(
    "/catalog",
    response_model=CatalogList,
    response_model_exclude_none=True,
    operation_id="listCatalog",
    tags=["Catalog"],
    openapi_extra={"x-jplearn-fr": ["FR-CAT-002", "FR-CAT-003", "FR-CAT-004"]},
)
async def list_catalog(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_user),
    ci_level: int | None = Query(default=None, ge=0, le=4),
) -> CatalogList:
    query_port = create_catalog_query(session, request.app.state.settings)
    items_dto = await handle_list_published(
        ListPublishedCatalogQuery(ci_level=ci_level),
        query_port,
    )
    return CatalogList(
        items=[
            CatalogItemPublic(
                id=dto.id,
                ci_level=dto.ci_level,
                duration_seconds=dto.duration_seconds,
                media_type=dto.media_type,
                topic_id=dto.topic_id,
                visual_support=dto.visual_support,
                playback_url=dto.playback_url,
                hls_url=dto.hls_url,
            )
            for dto in items_dto
        ]
    )


@router.get(
    "/staff/catalog",
    response_model=CatalogStaffList,
    operation_id="listStaffCatalog",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CAT-005", "FR-CMS-001"]},
    responses={403: {"description": "Not teacher or admin"}},
)
async def list_staff_catalog(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_roles("teacher", "admin")),
    status: str | None = Query(default=None),
    ci_level: int | None = Query(default=None, ge=0, le=4),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CatalogStaffList:
    repo = create_catalog_repository(session)
    items_dto = await handle_list_staff_catalog(
        ListStaffCatalogQuery(status=status, ci_level=ci_level, limit=limit, offset=offset),
        repo,
    )
    return CatalogStaffList(
        items=[CatalogItemStaff(**asdict(dto)) for dto in items_dto],
    )


@router.get(
    "/staff/catalog/{id}",
    response_model=CatalogItemStaff,
    operation_id="getStaffCatalogItem",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CAT-005"]},
    responses={
        403: {"description": "Not teacher or admin"},
        404: {"description": "Catalog item not found"},
    },
)
async def get_staff_catalog_item(
    id: UUIDPath,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    repo = create_catalog_repository(session)
    try:
        dto = await handle_get_staff_catalog_item(GetStaffCatalogItemQuery(item_id=id), repo)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Catalog item not found") from exc
    return CatalogItemStaff(**asdict(dto))


@router.patch(
    "/staff/catalog/{id}",
    response_model=CatalogItemStaff,
    operation_id="updateStaffCatalogItem",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CAT-005"]},
    responses={
        400: {"description": "Item is not in draft status"},
        403: {"description": "Not teacher or admin"},
        404: {"description": "Catalog item not found"},
        409: {"description": "Revision conflict"},
    },
)
async def update_staff_catalog_item(
    id: UUIDPath,
    body: CatalogItemPatch,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    uow = create_uow(session)
    cmd = UpdateDraftCatalogItemCommand(
        item_id=id,
        revision=body.revision,
        topic_id=body.topic_id,
        ci_level=body.ci_level,
        duration_seconds=body.duration_seconds,
        media_type=body.media_type,
        visual_support=body.visual_support,
        title_internal=body.title_internal,
    )
    try:
        dto = await handle_update_draft_catalog_item(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CatalogItemStaff(**asdict(dto))



@router.post(
    "/staff/catalog",
    status_code=201,
    response_model=CatalogItemStaff,
    operation_id="createCatalogItem",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CAT-001", "FR-CAT-005"]},
    responses={403: {"description": "Not teacher or admin"}},
)
async def create_catalog_item(
    body: CatalogItemWrite,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    uow = create_uow(session)
    cmd = CreateCatalogItemCommand(
        topic_id=body.topic_id,
        ci_level=body.ci_level,
        duration_seconds=body.duration_seconds,
        media_type=body.media_type,
        visual_support=body.visual_support,
        title_internal=body.title_internal,
        created_by=user.id,
    )
    try:
        dto = await handle_create_catalog_item(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CatalogItemStaff(**asdict(dto))


@router.post(
    "/staff/catalog/{id}/submit-qa",
    response_model=CatalogItemStaff,
    operation_id="submitLevelQa",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-002"]},
)
async def submit_level_qa(
    id: UUIDPath,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserDTO = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    uow = create_uow(session)
    cmd = SubmitCatalogForQaCommand(item_id=id)
    try:
        dto = await handle_submit_qa(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CatalogItemStaff(**asdict(dto))


@router.post(
    "/staff/catalog/{id}/publish",
    response_model=CatalogItemStaff,
    operation_id="publishCatalogItem",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-002", "FR-CMS-003", "FR-CMS-004", "FR-CAT-002"]},
    responses={
        400: {"description": "Invalid status or missing media"},
        403: {"description": "Admin only"},
    },
)
async def publish_catalog_item(
    id: UUIDPath,
    request: Request,
    session: AsyncSession = Depends(get_session),
    storage: StoragePort = Depends(get_storage),
    _admin: UserDTO = Depends(require_roles("admin")),
) -> CatalogItemStaff:
    uow = create_uow(session)
    cmd = PublishCatalogItemCommand(item_id=id)
    try:
        dto = await handle_publish(cmd, uow, storage)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CatalogItemStaff(**asdict(dto))


@router.post(
    "/staff/catalog/{id}/unpublish",
    response_model=CatalogItemStaff,
    operation_id="unpublishCatalogItem",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-002", "FR-CAT-002"]},
    responses={
        400: {"description": "Item is not published"},
        403: {"description": "Admin only"},
        404: {"description": "Catalog item not found"},
    },
)
async def unpublish_catalog_item(
    id: UUIDPath,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin: UserDTO = Depends(require_roles("admin")),
) -> CatalogItemStaff:
    uow = create_uow(session)
    cmd = UnpublishCatalogItemCommand(item_id=id)
    try:
        dto = await handle_unpublish(cmd, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return CatalogItemStaff(**asdict(dto))
