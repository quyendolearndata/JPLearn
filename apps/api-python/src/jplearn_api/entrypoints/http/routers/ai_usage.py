"""HTTP endpoints for Staff AI Quota Accounts and Usage Ledger (ADR-007 PR8c).

Paths:
- GET /staff/ai-usage
- GET /staff/ai-usage/summary
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.handlers.ai_usage import (
    handle_get_ai_usage_summary,
    handle_get_my_ai_usage,
)
from jplearn_api.application.queries import (
    GetAiUsageSummaryQuery,
    GetMyAiUsageQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import (
    get_app_settings,
    get_session,
)
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.schemas import (
    AiUsageItemPublic,
    AiUsageListResponsePublic,
    AiUsageSummaryItemPublic,
    AiUsageSummaryResponsePublic,
)
from jplearn_api.settings import Settings

router = APIRouter(tags=["Staff AI Usage"])


@router.get(
    "/staff/ai-usage",
    response_model=AiUsageListResponsePublic,
    operation_id="getStaffAiUsage",
    openapi_extra={"x-jplearn-fr": ["FR-STAFF-001", "FR-AI-001"]},
)
async def get_my_ai_usage(
    from_date: datetime = Query(..., description="Start of date range (ISO 8601)"),
    to_date: datetime = Query(..., description="End of date range (ISO 8601)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: UserDTO = Depends(require_roles("teacher", "admin")),
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_session),
) -> AiUsageListResponsePublic:
    """List staff AI usage entries within date range (max 90 days)."""
    uow = create_uow(session)
    query = GetMyAiUsageQuery(
        user_id=user.id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    try:
        dto = await handle_get_my_ai_usage(
            query=query,
            uow=uow,
            capability_enabled=settings.staff_ai_enabled,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from None

    return AiUsageListResponsePublic(
        items=[
            AiUsageItemPublic(
                id=item.id,
                account_id=item.account_id,
                job_id=item.job_id,
                kind=item.kind,
                status=item.status,
                provider=item.provider,
                provider_request_id=item.provider_request_id,
                attempt=item.attempt,
                audio_seconds=item.audio_seconds,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                cost_micros=item.cost_micros,
                currency=item.currency,
                policy_version=item.policy_version,
                created_at=item.created_at,
                settled_at=item.settled_at,
                description=item.description,
            )
            for item in dto.items
        ],
        total_count=dto.total_count,
        from_date=dto.from_date,
        to_date=dto.to_date,
    )


@router.get(
    "/staff/ai-usage/summary",
    response_model=AiUsageSummaryResponsePublic,
    operation_id="getStaffAiUsageSummary",
    openapi_extra={"x-jplearn-fr": ["FR-ADMIN-001", "FR-AI-001"]},
)
async def get_ai_usage_summary(
    from_date: datetime = Query(..., description="Start of date range (ISO 8601)"),
    to_date: datetime = Query(..., description="End of date range (ISO 8601)"),
    _admin: UserDTO = Depends(require_roles("admin")),
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_session),
) -> AiUsageSummaryResponsePublic:
    """Admin-only aggregated AI usage summary across all accounts within date range (max 90 days)."""
    uow = create_uow(session)
    query = GetAiUsageSummaryQuery(
        from_date=from_date,
        to_date=to_date,
    )
    try:
        dto = await handle_get_ai_usage_summary(
            query=query,
            uow=uow,
            capability_enabled=settings.staff_ai_enabled,
        )
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from None

    return AiUsageSummaryResponsePublic(
        from_date=dto.from_date,
        to_date=dto.to_date,
        summary=[
            AiUsageSummaryItemPublic(
                provider=s.provider,
                currency=s.currency,
                date=s.date,
                total_audio_seconds=s.total_audio_seconds,
                total_input_tokens=s.total_input_tokens,
                total_output_tokens=s.total_output_tokens,
                total_cost_micros=s.total_cost_micros,
                events_count=s.events_count,
            )
            for s in dto.summary
        ],
        total_audio_seconds=dto.total_audio_seconds,
        total_input_tokens=dto.total_input_tokens,
        total_output_tokens=dto.total_output_tokens,
        total_cost_micros=dto.total_cost_micros,
    )
