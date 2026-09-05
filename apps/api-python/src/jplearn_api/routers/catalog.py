from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    CreateCatalogItemCommand,
    PublishCatalogItemCommand,
    SubmitCatalogForQaCommand,
    UnpublishCatalogItemCommand,
)
from jplearn_api.application.handlers.catalog import (
    handle_create_catalog_item,
    handle_list_published,
    handle_publish,
    handle_submit_qa,
    handle_unpublish,
)
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.queries import ListPublishedCatalogQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_catalog_query, create_catalog_repository, create_uow
from jplearn_api.deps import UUIDPath, get_session, get_storage
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.roles import require_roles
from jplearn_api.schemas import CatalogItemPublic, CatalogItemStaff, CatalogItemWrite, CatalogList
from jplearn_api.security import require_user

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
