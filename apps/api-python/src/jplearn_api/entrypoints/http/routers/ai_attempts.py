"""Staff attempt inspection and admin billing reconciliation, available with AI off."""

from dataclasses import asdict
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.handlers.ai_attempts import reconcile_ai_attempt
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.dependencies import UUIDPath, get_session
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
from jplearn_api.entrypoints.http.roles import require_roles

router = APIRouter(tags=["Staff AI Attempts"])


class AttemptUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_seconds: int = Field(ge=0, le=2147483647)
    input_tokens: int = Field(ge=0, le=2147483647)
    output_tokens: int = Field(ge=0, le=2147483647)
    cost_micros: int = Field(ge=0, le=2147483647)
    currency: Literal["USD"] = "USD"


class ReconcileAttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["billed", "not_billed"]
    evidence: str = Field(min_length=10, max_length=2000)
    provider_request_id: str | None = Field(default=None, min_length=1, max_length=200)
    usage: AttemptUsage | None = None


class AiAttemptPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    job_id: str
    attempt_number: int = Field(ge=1)
    provider: str
    idempotency_key: str
    state: Literal["running", "outcome_unknown", "settled", "not_billed"]
    lease_expires_at: datetime
    created_at: datetime
    updated_at: datetime
    provider_request_id: str | None = None
    usage: dict | None = None
    evidence: str | None = None
    resolved_by: str | None = None
    resolution_hash: str | None = None


@router.get(
    "/staff/content-jobs/{id}/attempts",
    response_model=list[AiAttemptPublic],
    operation_id="listStaffAiAttempts",
    openapi_extra={"x-jplearn-fr": ["FR-AI-001"]},
    responses={401: {"description": "Authentication required"}, 403: {"description": "Admin only"}},
)
async def list_attempts(
    id: UUIDPath, user: UserDTO = Depends(require_roles("admin")), session: AsyncSession = Depends(get_session)
) -> list[AiAttemptPublic]:
    async with create_uow(session) as uow:
        return [asdict(a) for a in await uow.content_jobs.list_job_attempts(id)]


@router.post(
    "/staff/content-jobs/{id}/attempts/{attempt_id}/reconcile",
    response_model=AiAttemptPublic,
    operation_id="reconcileStaffAiAttempt",
    openapi_extra={"x-jplearn-fr": ["FR-AI-001"]},
    responses={
        400: {"description": "Invalid reconciliation evidence or usage"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin only"},
        404: {"description": "Attempt not found"},
        409: {"description": "Attempt state or evidence conflict"},
    },
)
async def reconcile_attempt(
    id: UUIDPath,
    attempt_id: str,
    body: ReconcileAttemptRequest,
    user: UserDTO = Depends(require_roles("admin")),
    session: AsyncSession = Depends(get_session),
) -> AiAttemptPublic:
    try:
        attempt = await reconcile_ai_attempt(
            create_uow(session),
            job_id=id,
            attempt_id=attempt_id,
            user_id=user.id,
            user_roles=tuple(user.roles),
            decision=body.decision,
            evidence=body.evidence,
            provider_request_id=body.provider_request_id,
            usage=body.usage.model_dump() if body.usage else None,
        )
        return asdict(attempt)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc
