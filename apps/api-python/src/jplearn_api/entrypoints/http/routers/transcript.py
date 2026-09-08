"""HTTP endpoints for Staff Japanese Transcripts and Language Analysis (ADR-007 PR8a).

Paths:
- GET  /staff/catalog/{id}/transcript
- PUT  /staff/catalog/{id}/transcript
- POST /staff/catalog/{id}/transcript/submit-qa
- POST /staff/catalog/{id}/transcript/approve
- POST /staff/catalog/{id}/transcript/return-to-draft
- POST /staff/catalog/{id}/language-analysis-jobs
- GET  /staff/language-analysis-jobs/{id}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import (
    ApproveTranscriptCommand,
    CreateLanguageAnalysisJobCommand,
    ReturnTranscriptToDraftCommand,
    SaveTranscriptDraftCommand,
    SubmitTranscriptQACommand,
)
from jplearn_api.application.handlers.transcript import (
    handle_approve_transcript,
    handle_create_language_analysis_job,
    handle_get_language_analysis_job,
    handle_get_transcript,
    handle_return_transcript_to_draft,
    handle_save_transcript_draft,
    handle_submit_transcript_qa,
)
from jplearn_api.application.queries import (
    GetLanguageAnalysisJobQuery,
    GetTranscriptQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import (
    UUIDPath,
    get_session,
)
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    ApproveTranscriptBody,
    CreateLanguageAnalysisJobBody,
    LanguageAnalysisJobPublic,
    ReturnTranscriptToDraftBody,
    SaveTranscriptDraftBody,
    SubmitTranscriptQABody,
    TranscriptRevisionPublic,
    TranscriptSegmentPublic,
)

router = APIRouter(tags=["Staff Transcripts"])


def _to_public_rev(rev) -> TranscriptRevisionPublic:
    return TranscriptRevisionPublic(
        id=rev.id,
        catalog_item_id=rev.catalog_item_id,
        content_version_id=rev.content_version_id,
        revision=rev.revision,
        status=rev.status.value if hasattr(rev.status, "value") else str(rev.status),
        segments=[TranscriptSegmentPublic(scene_id=s.scene_id, text_ja=s.text_ja) for s in rev.segments],
        provenance=rev.provenance.value if hasattr(rev.provenance, "value") else str(rev.provenance),
        created_by=rev.created_by,
        approved_by=rev.approved_by,
        return_reason=rev.return_reason,
        created_at=rev.created_at,
        updated_at=rev.updated_at,
    )


def _to_public_job(job) -> LanguageAnalysisJobPublic:
    return LanguageAnalysisJobPublic(
        id=job.id,
        catalog_item_id=job.catalog_item_id,
        transcript_revision_id=job.transcript_revision_id,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        results=job.results,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/staff/catalog/{id}/transcript",
    response_model=TranscriptRevisionPublic,
    operation_id="getStaffCatalogTranscript",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Get transcript for catalog item",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Catalog item not found"},
    },
)
async def get_staff_transcript(
    id: UUIDPath,
    content_version_id: Annotated[str | None, Query(description="Content version ID (optional)")] = None,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> TranscriptRevisionPublic:
    uow = create_uow(session)
    query = GetTranscriptQuery(catalog_item_id=id, content_version_id=content_version_id)
    try:
        rev = await handle_get_transcript(query, uow)
        return _to_public_rev(rev)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


@router.put(
    "/staff/catalog/{id}/transcript",
    response_model=TranscriptRevisionPublic,
    operation_id="saveStaffCatalogTranscript",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Save draft transcript with expected_revision CAS",
    responses={
        400: {"description": "Validation error or invalid scene reference"},
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Catalog item not found"},
        409: {"description": "Revision conflict"},
    },
)
async def save_staff_transcript(
    id: UUIDPath,
    body: SaveTranscriptDraftBody,
    session: AsyncSession = Depends(get_session),
    staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> TranscriptRevisionPublic:
    uow = create_uow(session)
    cmd = SaveTranscriptDraftCommand(
        user_id=staff.id,
        catalog_item_id=id,
        content_version_id=body.content_version_id,
        expected_revision=body.expected_revision,
        segments=[s.model_dump() for s in body.segments],
        provenance=body.provenance,
    )
    try:
        rev = await handle_save_transcript_draft(cmd, uow)
        return _to_public_rev(rev)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


@router.post(
    "/staff/catalog/{id}/transcript/submit-qa",
    response_model=TranscriptRevisionPublic,
    operation_id="submitStaffCatalogTranscriptQA",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Submit draft transcript for QA review",
    responses={
        400: {"description": "Invalid state for QA submission"},
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Catalog item or transcript not found"},
        409: {"description": "Revision conflict"},
    },
)
async def submit_staff_transcript_qa(
    id: UUIDPath,
    body: SubmitTranscriptQABody,
    session: AsyncSession = Depends(get_session),
    staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> TranscriptRevisionPublic:
    uow = create_uow(session)
    cmd = SubmitTranscriptQACommand(
        user_id=staff.id,
        catalog_item_id=id,
        content_version_id=body.content_version_id,
        expected_revision=body.expected_revision,
    )
    try:
        rev = await handle_submit_transcript_qa(cmd, uow)
        return _to_public_rev(rev)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


@router.post(
    "/staff/catalog/{id}/transcript/approve",
    response_model=TranscriptRevisionPublic,
    operation_id="approveStaffCatalogTranscript",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Approve transcript revision and publish search projection",
    responses={
        400: {"description": "Invalid state for approval"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin only"},
        404: {"description": "Catalog item or transcript not found"},
        409: {"description": "Revision conflict"},
    },
)
async def approve_staff_transcript(
    id: UUIDPath,
    body: ApproveTranscriptBody,
    session: AsyncSession = Depends(get_session),
    admin: UserDTO = Depends(require_roles("admin")),
) -> TranscriptRevisionPublic:
    uow = create_uow(session)
    cmd = ApproveTranscriptCommand(
        user_id=admin.id,
        catalog_item_id=id,
        content_version_id=body.content_version_id,
        expected_revision=body.expected_revision,
    )
    try:
        rev = await handle_approve_transcript(cmd, uow)
        return _to_public_rev(rev)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


@router.post(
    "/staff/catalog/{id}/transcript/return-to-draft",
    response_model=TranscriptRevisionPublic,
    operation_id="returnStaffCatalogTranscriptToDraft",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Return transcript revision to draft with reason",
    responses={
        400: {"description": "Validation error or invalid state"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin only"},
        404: {"description": "Catalog item or transcript not found"},
        409: {"description": "Revision conflict"},
    },
)
async def return_staff_transcript_to_draft(
    id: UUIDPath,
    body: ReturnTranscriptToDraftBody,
    session: AsyncSession = Depends(get_session),
    admin: UserDTO = Depends(require_roles("admin")),
) -> TranscriptRevisionPublic:
    uow = create_uow(session)
    cmd = ReturnTranscriptToDraftCommand(
        user_id=admin.id,
        catalog_item_id=id,
        content_version_id=body.content_version_id,
        expected_revision=body.expected_revision,
        reason=body.reason,
    )
    try:
        rev = await handle_return_transcript_to_draft(cmd, uow)
        return _to_public_rev(rev)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


@router.post(
    "/staff/catalog/{id}/language-analysis-jobs",
    response_model=LanguageAnalysisJobPublic,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="createLanguageAnalysisJob",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Create language analysis job for transcript revision",
    responses={
        202: {"description": "Language analysis job accepted"},
        400: {"description": "Validation error"},
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Catalog item or transcript revision not found"},
    },
)
async def create_language_analysis_job(
    id: UUIDPath,
    body: CreateLanguageAnalysisJobBody,
    session: AsyncSession = Depends(get_session),
    staff: UserDTO = Depends(require_roles("teacher", "admin")),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> LanguageAnalysisJobPublic:
    uow = create_uow(session)
    cmd = CreateLanguageAnalysisJobCommand(
        user_id=staff.id,
        catalog_item_id=id,
        transcript_revision_id=body.transcript_revision_id,
        idempotency_key=idempotency_key,
    )
    try:
        job = await handle_create_language_analysis_job(cmd, uow)
        return _to_public_job(job)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc


@router.get(
    "/staff/language-analysis-jobs/{id}",
    response_model=LanguageAnalysisJobPublic,
    operation_id="getLanguageAnalysisJob",
    openapi_extra={"x-jplearn-fr": ["FR-JPA-001"]},
    summary="Get language analysis job details",
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Staff only"},
        404: {"description": "Language analysis job not found"},
    },
)
async def get_language_analysis_job(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    _staff: UserDTO = Depends(require_roles("teacher", "admin")),
) -> LanguageAnalysisJobPublic:
    uow = create_uow(session)
    query = GetLanguageAnalysisJobQuery(job_id=id)
    try:
        job = await handle_get_language_analysis_job(query, uow)
        return _to_public_job(job)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
