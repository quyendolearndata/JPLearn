from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api import catalog_service
from jplearn_api.deps import UUIDPath, get_session, get_storage
from jplearn_api.models import User
from jplearn_api.roles import require_roles
from jplearn_api.schemas import (CatalogItemStaff, CatalogItemWrite, CatalogList, CatalogItemPatch,
    CatalogReviewBody, CatalogItemDetail, CatalogStaffList)
from jplearn_api.security import require_user
from jplearn_api.storage import StoragePort

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
    _user: User = Depends(require_user),
    ci_level: int | None = Query(default=None, ge=0, le=4),
) -> CatalogList:
    return CatalogList(items=await catalog_service.list_published(session, request.app.state.settings, ci_level))


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
    user: User = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    return await catalog_service.create(session, request.app.state.settings, body, user.id)


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
    _user: User = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    return await catalog_service.submit_qa(session, request.app.state.settings, id)


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
    _admin: User = Depends(require_roles("admin")),
) -> CatalogItemStaff:
    return await catalog_service.publish(session, request.app.state.settings, storage, id)


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
    _admin: User = Depends(require_roles("admin")),
) -> CatalogItemStaff:
    return await catalog_service.unpublish(session, request.app.state.settings, id)


STAFF_ERRORS = {
    400: {"description": "Invalid input or workflow state"},
    401: {"description": "Missing or invalid Bearer"},
    403: {"description": "Not teacher or admin"},
    404: {"description": "Catalog item not found"},
    500: {"description": "Internal server error"},
}


@router.get(
    "/staff/catalog", response_model=CatalogStaffList, operation_id="listStaffCatalog",
    tags=["CMS"], responses=STAFF_ERRORS,
    openapi_extra={"x-jplearn-fr": ["FR-CAT-005", "NFR-SEC-002"]},
)
async def list_staff_catalog(
    request: Request,
    status: Literal["draft", "level_qa", "published", "archived"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_roles("teacher", "admin")),
) -> CatalogStaffList:
    return CatalogStaffList(items=await catalog_service.list_staff(
        session, request.app.state.settings, status, limit, offset,
    ))


@router.get(
    "/staff/catalog/{id}", response_model=CatalogItemDetail, operation_id="getStaffCatalogItem",
    tags=["CMS"], responses=STAFF_ERRORS,
    openapi_extra={"x-jplearn-fr": ["FR-CAT-005", "FR-CMS-002", "NFR-SEC-002"]},
)
async def get_staff_catalog_item(
    id: UUIDPath, request: Request,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_roles("teacher", "admin")),
) -> CatalogItemDetail:
    return await catalog_service.detail(session, request.app.state.settings, id)


@router.patch(
    "/staff/catalog/{id}", response_model=CatalogItemStaff, operation_id="updateDraftCatalogItem",
    tags=["CMS"], responses=STAFF_ERRORS,
    openapi_extra={"x-jplearn-fr": ["FR-CAT-005", "NFR-SEC-002"]},
)
async def update_draft_catalog_item(
    id: UUIDPath, body: CatalogItemPatch, request: Request,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    return await catalog_service.update_draft(session, request.app.state.settings, id, body)


@router.post(
    "/staff/catalog/{id}/review", response_model=CatalogItemStaff, operation_id="reviewCatalogItem",
    tags=["CMS"], responses=STAFF_ERRORS,
    openapi_extra={"x-jplearn-fr": ["FR-CMS-002", "NFR-SEC-002"]},
)
async def review_catalog_item(
    id: UUIDPath, body: CatalogReviewBody, request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_roles("teacher", "admin")),
) -> CatalogItemStaff:
    return await catalog_service.review(session, request.app.state.settings, id, body, user.id)
