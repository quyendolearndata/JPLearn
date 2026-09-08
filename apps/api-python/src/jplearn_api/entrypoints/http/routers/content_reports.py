"""HTTP router for content reports and staff moderation (UC-L24, UC-T09, FR-RPT-001)."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    CreateContentReportCommand,
    PatchStaffContentReportCommand,
)
from jplearn_api.application.handlers.content_reports import (
    handle_create_report,
    handle_get_my_report,
    handle_get_staff_report,
    handle_list_my_reports,
    handle_list_staff_reports,
    handle_patch_staff_report,
)
from jplearn_api.application.queries import (
    GetMyContentReportQuery,
    GetStaffContentReportQuery,
    ListMyContentReportsQuery,
    ListStaffContentReportsQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.content_report import ContentReport, ContentReportAudit
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session, require_capability
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    ContentReportAuditPublic,
    ContentReportLearnerPublic,
    ContentReportStaffDetailPublic,
    ContentReportStaffPublic,
    CreateContentReportBody,
    PatchStaffContentReportBody,
)
from jplearn_api.entrypoints.http.security import require_user

router = APIRouter(tags=["Content Reports"])


def _to_learner_public(report: ContentReport) -> ContentReportLearnerPublic:
    category_val = report.category.value if hasattr(report.category, "value") else str(report.category)
    status_val = report.status.value if hasattr(report.status, "value") else str(report.status)
    return ContentReportLearnerPublic(
        id=report.id,
        catalog_item_id=report.catalog_item_id,
        content_version_id=report.content_version_id,
        scene_id=report.scene_id,
        position_ms=report.position_ms,
        category=category_val,  # type: ignore[arg-type]
        description=report.description,
        status=status_val,  # type: ignore[arg-type]
        public_reply=report.public_reply,
        resolution_version_id=report.resolution_version_id,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _to_staff_public(report: ContentReport) -> ContentReportStaffPublic:
    category_val = report.category.value if hasattr(report.category, "value") else str(report.category)
    status_val = report.status.value if hasattr(report.status, "value") else str(report.status)
    return ContentReportStaffPublic(
        id=report.id,
        user_id=report.user_id,
        catalog_item_id=report.catalog_item_id,
        content_version_id=report.content_version_id,
        scene_id=report.scene_id,
        position_ms=report.position_ms,
        category=category_val,  # type: ignore[arg-type]
        description=report.description,
        status=status_val,  # type: ignore[arg-type]
        revision=report.revision,
        assignee_id=report.assignee_id,
        public_reply=report.public_reply,
        internal_note=report.internal_note,
        resolution_version_id=report.resolution_version_id,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _to_staff_detail_public(
    report: ContentReport, audits: list[ContentReportAudit]
) -> ContentReportStaffDetailPublic:
    base = _to_staff_public(report)
    audit_dtos = [
        ContentReportAuditPublic(
            id=a.id,
            report_id=a.report_id,
            actor_id=a.actor_id,
            from_status=a.from_status.value if hasattr(a.from_status, "value") else str(a.from_status) if a.from_status else None,
            to_status=a.to_status.value if hasattr(a.to_status, "value") else str(a.to_status),
            revision=a.revision,
            reason=a.reason,
            created_at=a.created_at,
        )
        for a in audits
    ]
    return ContentReportStaffDetailPublic(
        **base.model_dump(),
        audit_logs=audit_dtos,
    )


@router.post(
    "/catalog/{id}/reports",
    response_model=ContentReportLearnerPublic,
    operation_id="createContentReport",
    openapi_extra={"x-jplearn-fr": ["FR-RPT-001", "FR-LRN-001"]},
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "description": "Report already filed (idempotent replay)",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ContentReportLearnerPublic"}
                }
            },
        },
        201: {
            "description": "Report successfully filed",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ContentReportLearnerPublic"}
                }
            },
        },
        400: {"description": "Invalid parameters, out of bounds position, or unpublished item/version"},
        401: {"description": "Authentication required"},
        404: {"description": "Catalog item not found"},
        409: {"description": "Idempotency key reused with different request parameters"},
        429: {"description": "Daily report quota exceeded (max 10 per day)"},
    },
)
async def create_report(
    id: UUIDPath,
    body: CreateContentReportBody,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    _cap: None = Depends(require_capability("content_reports_enabled")),
) -> ContentReportLearnerPublic:
    cmd = CreateContentReportCommand(
        user_id=user.id,
        catalog_item_id=id,
        content_version_id=body.content_version_id,
        scene_id=body.scene_id,
        position_ms=body.position_ms,
        category=body.category,
        description=body.description,
        idempotency_key=idempotency_key,
    )
    try:
        async with create_uow(session) as uow:
            report = await handle_create_report(cmd, uow)
            await uow.commit()
    except DomainError as exc:
        raise map_domain_error_to_http(exc)

    return _to_learner_public(report)


@router.get(
    "/me/content-reports",
    response_model=list[ContentReportLearnerPublic],
    operation_id="listMyContentReports",
    openapi_extra={"x-jplearn-fr": ["FR-RPT-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "List of user filed content reports"},
        401: {"description": "Authentication required"},
    },
)
async def list_my_reports(
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[ContentReportLearnerPublic]:
    query = ListMyContentReportsQuery(user_id=user.id, limit=limit, offset=offset)
    try:
        async with create_uow(session) as uow:
            reports, total = await handle_list_my_reports(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc)

    response.headers["X-Total-Count"] = str(total)
    return [_to_learner_public(r) for r in reports]


@router.get(
    "/me/content-reports/{id}",
    response_model=ContentReportLearnerPublic,
    operation_id="getMyContentReport",
    openapi_extra={"x-jplearn-fr": ["FR-RPT-001", "FR-LRN-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Details of user content report"},
        401: {"description": "Authentication required"},
        404: {"description": "Report not found"},
    },
)
async def get_my_report(
    id: UUIDPath,
    user: UserDTO = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> ContentReportLearnerPublic:
    query = GetMyContentReportQuery(user_id=user.id, report_id=id)
    try:
        async with create_uow(session) as uow:
            report = await handle_get_my_report(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc)

    return _to_learner_public(report)


@router.get(
    "/staff/content-reports",
    response_model=list[ContentReportStaffPublic],
    operation_id="listStaffContentReports",
    openapi_extra={"x-jplearn-fr": ["FR-RPT-001", "FR-STF-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Moderation queue of content reports"},
        401: {"description": "Authentication required"},
        403: {"description": "Forbidden to non-staff"},
    },
)
async def list_staff_reports(
    response: Response,
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    catalog_item_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    staff: UserDTO = Depends(require_roles("teacher", "admin")),
    session: AsyncSession = Depends(get_session),
) -> list[ContentReportStaffPublic]:
    query = ListStaffContentReportsQuery(
        status=status,
        category=category,
        catalog_item_id=catalog_item_id,
        limit=limit,
        offset=offset,
    )
    try:
        async with create_uow(session) as uow:
            reports, total = await handle_list_staff_reports(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc)

    response.headers["X-Total-Count"] = str(total)
    return [_to_staff_public(r) for r in reports]


@router.get(
    "/staff/content-reports/{id}",
    response_model=ContentReportStaffDetailPublic,
    operation_id="getStaffContentReport",
    openapi_extra={"x-jplearn-fr": ["FR-RPT-001", "FR-STF-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Detailed staff content report with audit logs"},
        401: {"description": "Authentication required"},
        403: {"description": "Forbidden to non-staff"},
        404: {"description": "Report not found"},
    },
)
async def get_staff_report(
    id: UUIDPath,
    staff: UserDTO = Depends(require_roles("teacher", "admin")),
    session: AsyncSession = Depends(get_session),
) -> ContentReportStaffDetailPublic:
    query = GetStaffContentReportQuery(report_id=id)
    try:
        async with create_uow(session) as uow:
            report, audits = await handle_get_staff_report(query, uow)
    except DomainError as exc:
        raise map_domain_error_to_http(exc)

    return _to_staff_detail_public(report, audits)


@router.patch(
    "/staff/content-reports/{id}",
    response_model=ContentReportStaffPublic,
    operation_id="patchStaffContentReport",
    openapi_extra={"x-jplearn-fr": ["FR-RPT-001", "FR-STF-001"]},
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Content report successfully updated"},
        400: {"description": "Invalid status or resolution version"},
        401: {"description": "Authentication required"},
        403: {"description": "Forbidden to non-staff"},
        404: {"description": "Report not found"},
        409: {"description": "Revision conflict (OCC)"},
    },
)
async def patch_staff_report(
    id: UUIDPath,
    body: PatchStaffContentReportBody,
    staff: UserDTO = Depends(require_roles("teacher", "admin")),
    session: AsyncSession = Depends(get_session),
) -> ContentReportStaffPublic:
    cmd = PatchStaffContentReportCommand(
        report_id=id,
        expected_revision=body.expected_revision,
        actor_id=staff.id,
        status=body.status,
        assignee_id=body.assignee_id,
        public_reply=body.public_reply,
        internal_note=body.internal_note,
        resolution_version_id=body.resolution_version_id,
        reason=body.reason,
    )
    try:
        async with create_uow(session) as uow:
            updated = await handle_patch_staff_report(cmd, uow)
            await uow.commit()
    except DomainError as exc:
        raise map_domain_error_to_http(exc)

    return _to_staff_public(updated)
