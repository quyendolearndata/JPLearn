from dataclasses import asdict
from typing import Literal
from jplearn_api.application.handlers.catalog import handle_review_catalog
from jplearn_api.entrypoints.http.schemas import CatalogReviewBody, CatalogItemDetail

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
from jplearn_api.application.handlers.search import handle_search_scenes
from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.application.queries import (
    GetStaffCatalogItemQuery,
    ListPublishedCatalogQuery,
    ListStaffCatalogQuery,
    SearchScenesQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_catalog_query, create_catalog_repository, create_uow, create_media_signer
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_app_settings, get_session, get_storage
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
    HighlightSpan,
    SearchResponsePublic,
    SearchResultItemPublic,
)
from jplearn_api.entrypoints.http.security import require_user
from jplearn_api.settings import Settings
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
    "/catalog/search",
    response_model=SearchResponsePublic,
    operation_id="searchScenes",
    tags=["Catalog"],
    openapi_extra={"x-jplearn-fr": ["FR-SCH-001", "FR-SCH-002", "FR-NEG"]},
    responses={
        400: {"description": "Invalid search query"},
        401: {"description": "Authentication required"},
        403: {"description": "Scene search capability disabled"},
        409: {"description": "Index generation mismatch"},
    },
)
async def search_catalog_scenes(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
    settings: Settings = Depends(get_app_settings),
    q: str = Query(..., min_length=1, max_length=100, description="Japanese search query"),
    ci_level: int | None = Query(default=None, ge=0, le=4, description="Filter CI level"),
    cursor: str | None = Query(default=None, description="Opaque pagination cursor"),
    limit: int = Query(default=20, ge=1, le=50, description="Page limit"),
) -> SearchResponsePublic:
    uow = create_uow(session)
    query = SearchScenesQuery(
        q=q,
        user_id=user.id,
        ci_level=ci_level,
        cursor=cursor,
        limit=limit,
    )
    try:
        dto = await handle_search_scenes(
            query=query,
            uow=uow,
            search_enabled=settings.scene_search_enabled,
        )
        return SearchResponsePublic(
            items=[
                SearchResultItemPublic(
                    catalog_item_id=it.catalog_item_id,
                    content_version_id=it.content_version_id,
                    scene_id=it.scene_id,
                    scene_index=it.scene_index,
                    start_time_seconds=it.start_time_seconds,
                    end_time_seconds=it.end_time_seconds,
                    matched_text_ja=it.matched_text_ja,
                    highlight_spans=[
                        HighlightSpan(start_offset=s["start_offset"], end_offset=s["end_offset"])
                        for s in it.highlight_spans
                    ],
                    match_kind=it.match_kind,  # type: ignore[arg-type]
                    ci_level=it.ci_level,
                    topic_id=it.topic_id,
                    title_jp=it.title_jp,
                )
                for it in dto.items
            ],
            next_cursor=dto.next_cursor,
            total_estimated=dto.total_estimated,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


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
    status: Literal["draft", "level_qa", "published", "archived"] | None = Query(default=None),
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
    response_model=CatalogItemDetail,
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
    from jplearn_api.application.handlers.catalog import _to_staff_dto
    from jplearn_api.entrypoints.http.datetime_adapt import to_json_z
    signer = create_media_signer(request.app.state.settings)
    async with create_uow(session) as uow:
        item = await uow.catalog.get_by_id_for_update(id)
        if item is None:
            raise HTTPException(status_code=404, detail="Catalog item not found")
        return CatalogItemDetail(
            **asdict(_to_staff_dto(item)),
            reviews=[dict(asdict(r), reviewed_at=to_json_z(r.reviewed_at)) for r in item.reviews],
            media=[dict(id=m.id, catalog_item_id=id, storage_key=m.storage_key,
                        playback_url=signer.sign_playback_url(m.id),
                        hls_url=signer.sign_hls_url(m.id) if m.hls_url else None, mime=m.mime,
                        measured_duration_ms=m.measured_duration_ms, source_sha256=m.source_sha256,
                        hls_bundle_sha256=m.hls_bundle_sha256) for m in item.media],
        )


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


@router.post("/staff/catalog/{id}/review", response_model=CatalogItemStaff,
    operation_id="reviewCatalogItem", tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-002", "NFR-SEC-002"]},
    responses={400: {"description": "Invalid review or workflow state"}, 403: {"description": "Not teacher or admin"}, 404: {"description": "Catalog item not found"}})
async def review_catalog_item(id: UUIDPath, body: CatalogReviewBody,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_roles("teacher", "admin"))) -> CatalogItemStaff:
    try:
        dto = await handle_review_catalog(id, body.decision, body.notes, user.id, create_uow(session))
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
    return CatalogItemStaff(**asdict(dto))
