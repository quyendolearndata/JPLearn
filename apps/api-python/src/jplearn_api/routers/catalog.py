from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api import catalog_service
from jplearn_api.deps import get_session
from jplearn_api.models import User
from jplearn_api.roles import require_roles
from jplearn_api.schemas import CatalogItemStaff, CatalogItemWrite, CatalogList
from jplearn_api.security import require_user

router = APIRouter()


def _parse_ci_level(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        number = float(raw)
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return None


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
    ci_level: str | None = Query(default=None),
) -> CatalogList:
    parsed = _parse_ci_level(ci_level)
    return CatalogList(items=await catalog_service.list_published(session, request.app.state.settings, parsed))


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
    id: str,
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
    responses={403: {"description": "Admin only"}},
)
async def publish_catalog_item(
    id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_roles("admin")),
) -> CatalogItemStaff:
    return await catalog_service.publish(session, request.app.state.settings, id)


@router.post(
    "/staff/catalog/{id}/unpublish",
    response_model=CatalogItemStaff,
    operation_id="unpublishCatalogItem",
    tags=["CMS"],
    openapi_extra={"x-jplearn-fr": ["FR-CMS-002", "FR-CAT-002"]},
    responses={403: {"description": "Admin only"}},
)
async def unpublish_catalog_item(
    id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_roles("admin")),
) -> CatalogItemStaff:
    return await catalog_service.unpublish(session, request.app.state.settings, id)
