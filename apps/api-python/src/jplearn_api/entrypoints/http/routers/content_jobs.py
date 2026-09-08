"""HTTP endpoints for Staff AI Content Jobs (ADR-007 PR8).

Paths:
- POST /staff/catalog/{id}/content-jobs
- GET  /staff/content-jobs/{id}
- POST /staff/content-jobs/{id}/cancel
- POST /staff/content-jobs/{id}/apply
"""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    ApplyContentJobCommand,
    CancelContentJobCommand,
    CreateContentJobCommand,
)
from jplearn_api.application.handlers.content_jobs import (
    AiPricingPolicy,
    handle_apply_content_job,
    handle_cancel_content_job,
    handle_create_content_job,
    handle_get_content_job,
)
from jplearn_api.application.queries import GetContentJobQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import (
    UUIDPath,
    get_app_settings,
    get_session,
)
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    ApplyContentJobRequest,
    ContentJobResponsePublic,
    CreateContentJobRequest,
)
from jplearn_api.settings import Settings

router = APIRouter(tags=["Staff Content Jobs"])


@router.post(
    "/staff/catalog/{id}/content-jobs",
    response_model=ContentJobResponsePublic,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createStaffContentJob",
    openapi_extra={"x-jplearn-fr": ["FR-STAFF-001", "FR-AI-001"]},
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Catalog item or content version not found"},
        409: {"description": "Conflict or active job already exists"},
    },
)
async def create_content_job(
    id: UUIDPath,
    body: CreateContentJobRequest,
    user: UserDTO = Depends(require_roles("teacher", "admin")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_session),
) -> ContentJobResponsePublic:
    """Create a durable content job for AI transcription or segmentation."""
    resolved_idem = idempotency_key or str(uuid4())
    uow = create_uow(session)
    payload = body.model_dump()
    cmd = CreateContentJobCommand(
        catalog_item_id=id,
        content_version_id=payload["content_version_id"],
        task=payload["task"],
        language=payload["language"],
        idempotency_key=resolved_idem,
        user_id=user.id,
        estimated_audio_seconds=payload["estimated_audio_seconds"],
        estimated_cost_micros=payload["estimated_cost_micros"],
    )
    try:
        dto = await handle_create_content_job(
            cmd,
            uow,
            capability_enabled=settings.staff_ai_enabled,
            pricing_policy=AiPricingPolicy(
                version=settings.ai_pricing_version,
                transcript_micros_per_audio_second=settings.ai_transcript_micros_per_audio_second,
                segmentation_micros_per_audio_second=settings.ai_segmentation_micros_per_audio_second,
            ),
        )
        return ContentJobResponsePublic.model_validate(dto.__dict__)
    except DomainError as err:
        raise map_domain_error_to_http(err) from err


@router.get(
    "/staff/content-jobs/{id}",
    response_model=ContentJobResponsePublic,
    operation_id="getStaffContentJob",
    openapi_extra={"x-jplearn-fr": ["FR-STAFF-001", "FR-AI-001"]},
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Content job not found"},
    },
)
async def get_content_job(
    id: UUIDPath,
    user: UserDTO = Depends(require_roles("teacher", "admin")),
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_session),
) -> ContentJobResponsePublic:
    """Retrieve content job status, progress, and draft results."""
    uow = create_uow(session)
    query = GetContentJobQuery(
        job_id=id,
        user_id=user.id,
        user_roles=tuple(user.roles),
    )
    try:
        dto = await handle_get_content_job(
            query,
            uow,
            capability_enabled=settings.staff_ai_enabled,
        )
        return ContentJobResponsePublic.model_validate(dto.__dict__)
    except DomainError as err:
        raise map_domain_error_to_http(err) from err


@router.post(
    "/staff/content-jobs/{id}/cancel",
    response_model=ContentJobResponsePublic,
    operation_id="cancelStaffContentJob",
    openapi_extra={"x-jplearn-fr": ["FR-STAFF-001", "FR-AI-001"]},
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Content job not found"},
        409: {"description": "Cannot cancel completed job"},
    },
)
async def cancel_content_job(
    id: UUIDPath,
    user: UserDTO = Depends(require_roles("teacher", "admin")),
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_session),
) -> ContentJobResponsePublic:
    """Cancel a queued or running content job."""
    uow = create_uow(session)
    cmd = CancelContentJobCommand(
        job_id=id,
        user_id=user.id,
        user_roles=tuple(user.roles),
    )
    try:
        dto = await handle_cancel_content_job(
            cmd,
            uow,
            capability_enabled=settings.staff_ai_enabled,
        )
        return ContentJobResponsePublic.model_validate(dto.__dict__)
    except DomainError as err:
        raise map_domain_error_to_http(err) from err


@router.post(
    "/staff/content-jobs/{id}/apply",
    response_model=ContentJobResponsePublic,
    operation_id="applyStaffContentJob",
    openapi_extra={"x-jplearn-fr": ["FR-STAFF-001", "FR-AI-001"]},
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Content job not found"},
        409: {"description": "CAS Revision conflict or source changed"},
    },
)
async def apply_content_job(
    id: UUIDPath,
    body: ApplyContentJobRequest,
    user: UserDTO = Depends(require_roles("teacher", "admin")),
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_session),
) -> ContentJobResponsePublic:
    """Apply generated segments to transcript draft with CAS revision check."""
    uow = create_uow(session)
    cmd = ApplyContentJobCommand(
        job_id=id,
        expected_revision=body.expected_revision,
        user_id=user.id,
        segments=body.segments,
    )
    try:
        dto = await handle_apply_content_job(
            cmd,
            uow,
            capability_enabled=settings.staff_ai_enabled,
        )
        return ContentJobResponsePublic.model_validate(dto.__dict__)
    except DomainError as err:
        raise map_domain_error_to_http(err) from err
