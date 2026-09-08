"""Application handlers for AI Content Jobs (ADR-007 PR8)."""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from jplearn_api.application.commands import (
    ApplyContentJobCommand,
    CancelContentJobCommand,
    CreateContentJobCommand,
    ReserveQuotaCommand,
    SaveTranscriptDraftCommand,
)
from jplearn_api.application.handlers.ai_attempts import mark_attempt_unknown
from jplearn_api.application.handlers.ai_usage import (
    handle_reserve_quota,
)
from jplearn_api.application.handlers.transcript import handle_save_transcript_draft
from jplearn_api.application.ports.ai_provider import AiTranscriptionPort
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import GetContentJobQuery
from jplearn_api.application.read_models import ContentJobDTO
from jplearn_api.domain.ai_attempt import AiAttempt
from jplearn_api.domain.content_job import (
    ContentJob,
    ContentJobStatus,
    ContentJobTask,
)
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    ForbiddenError,
    InvalidDomainStateError,
)

logger = logging.getLogger("jplearn.content_jobs")


@dataclass(frozen=True)
class AiPricingPolicy:
    """Versioned server-owned rates used to reserve AI budget."""

    version: str = "trial-2026-09-08"
    transcript_micros_per_audio_second: int = 1_000
    segmentation_micros_per_audio_second: int = 1_000

    def rate_for(self, task: ContentJobTask) -> int:
        if task == ContentJobTask.TRANSCRIPT:
            return self.transcript_micros_per_audio_second
        return self.segmentation_micros_per_audio_second


def _job_source_identity(version: Any, media_ref: Any) -> tuple[str, str, str]:
    storage_key = version.media_storage_key or media_ref.storage_key
    checksum = version.source_sha256 or media_ref.source_sha256 or "unverified"
    identity = f"{version.id}:{version.revision}:{storage_key}"
    if checksum != "unverified":
        identity = f"{identity}:{checksum}"
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return storage_key, checksum, digest


def to_content_job_dto(job: ContentJob) -> ContentJobDTO:
    """Project domain ContentJob into ContentJobDTO."""
    status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
    task_str = job.task.value if hasattr(job.task, "value") else str(job.task)
    return ContentJobDTO(
        id=job.id,
        catalog_item_id=job.catalog_item_id,
        content_version_id=job.content_version_id,
        task=task_str,
        language=job.language,
        status=status_str,
        progress=job.progress,
        provenance=job.provenance,
        result_draft=job.result_draft,
        error_message=job.error_message,
        applied_at=job.applied_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def handle_create_content_job(
    cmd: CreateContentJobCommand,
    uow: AsyncUnitOfWork,
    *,
    capability_enabled: bool = True,
    pricing_policy: AiPricingPolicy | None = None,
    id_generator: Any = lambda: str(uuid4()),
) -> ContentJobDTO:
    """Create a new AI transcription or segmentation job with quota reservation."""
    if not capability_enabled:
        raise ForbiddenError("Staff AI capability is disabled")

    try:
        task_enum = ContentJobTask(cmd.task)
    except ValueError:
        raise InvalidDomainStateError(f"Unsupported task '{cmd.task}'") from None

    async with uow:
        # 1. Idempotency check per user + key
        existing_idem = await uow.content_jobs.get_by_idempotency_key(cmd.user_id, cmd.idempotency_key)
        if existing_idem is not None:
            return to_content_job_dto(existing_idem)

        # 2. Validate catalog item and content version exist
        item = await uow.catalog.get_by_id(cmd.catalog_item_id)
        if item is None:
            raise EntityNotFoundError(f"Catalog item '{cmd.catalog_item_id}' not found")

        version = await uow.content.get_by_id(cmd.content_version_id)
        if version is None or version.catalog_item_id != cmd.catalog_item_id:
            raise EntityNotFoundError(
                f"Content version '{cmd.content_version_id}' not found for catalog item '{cmd.catalog_item_id}'"
            )

        # 3. Media asset verification via catalog item aggregate
        media_ref = item.media[0] if item.media else None
        if media_ref is None:
            raise InvalidDomainStateError(f"No media asset found for catalog item '{cmd.catalog_item_id}'")

        # 4. Check for active job on this version and task
        active_job = await uow.content_jobs.find_active_job(cmd.content_version_id, task_enum)
        if active_job is not None:
            raise ConflictError(
                f"An active job '{active_job.id}' is already running for task "
                f"'{cmd.task}' on version '{cmd.content_version_id}'"
            )

        # 5. Server-side quota estimation & verification (P1.11, P1.12)
        if cmd.estimated_audio_seconds < 0:
            raise InvalidDomainStateError("estimated_audio_seconds must be non-negative")
        if cmd.estimated_cost_micros < 0:
            raise InvalidDomainStateError("estimated_cost_micros must be non-negative")

        policy = pricing_policy or AiPricingPolicy()
        if not policy.version.strip():
            raise InvalidDomainStateError("AI pricing policy version must not be empty")
        rate_micros = policy.rate_for(task_enum)
        if rate_micros < 0:
            raise InvalidDomainStateError("AI pricing rate must be non-negative")

        # The request estimates are retained only for wire compatibility. Budget
        # admission is derived from the source observed and pinned by the server.
        measured_duration_ms = version.measured_duration_ms or media_ref.measured_duration_ms
        if measured_duration_ms is not None:
            server_estimated_seconds = math.ceil(measured_duration_ms / 1000)
            duration_basis = "media_probe"
        else:
            server_estimated_seconds = version.duration_seconds or item.duration_seconds or 0
            duration_basis = version.duration_source if version.duration_seconds else "catalog_metadata"
        if server_estimated_seconds <= 0:
            raise InvalidDomainStateError("AI jobs require a positive server-observed media duration")
        server_estimated_cost = server_estimated_seconds * rate_micros

        quota_acc = await uow.quota.get_or_create_account_for_user(cmd.user_id)

        job_id = id_generator()
        await handle_reserve_quota(
            ReserveQuotaCommand(
                account_id=quota_acc.id,
                user_id=cmd.user_id,
                idempotency_key=f"job_reserve_{cmd.idempotency_key}",
                provider="trial_transcriber",
                audio_seconds=server_estimated_seconds,
                input_tokens=0,
                output_tokens=0,
                cost_micros=server_estimated_cost,
                job_id=job_id,
                description=f"Reservation for {cmd.task} job {job_id}",
            ),
            uow,
            auto_commit=False,
        )

        source_storage_key, source_checksum, source_hash = _job_source_identity(version, media_ref)
        config_hash = hashlib.sha256(f"{cmd.task}:{cmd.language}:{policy.version}:{rate_micros}".encode()).hexdigest()

        now = datetime.now(UTC)
        job = ContentJob(
            id=job_id,
            catalog_item_id=cmd.catalog_item_id,
            content_version_id=cmd.content_version_id,
            task=task_enum,
            language=cmd.language,
            status=ContentJobStatus.QUEUED,
            progress=0.0,
            provenance={
                "provider": "trial_transcriber",
                "created_by": cmd.user_id,
                "source_storage_key": source_storage_key,
                "source_duration_seconds": server_estimated_seconds,
                "source_duration_basis": duration_basis,
                "source_sha256": source_checksum if source_checksum != "unverified" else None,
                "source_revision": version.revision,
                "pricing_version": policy.version,
                "pricing_rate_micros_per_audio_second": rate_micros,
                "reserved_cost_micros": server_estimated_cost,
            },
            source_hash=source_hash,
            config_hash=config_hash,
            idempotency_key=cmd.idempotency_key,
            created_by=cmd.user_id,
            attempt=0,
            max_attempts=3,
            created_at=now,
            updated_at=now,
        )
        await uow.content_jobs.add(job)
        await uow.commit()

        return to_content_job_dto(job)


async def handle_get_content_job(
    query: GetContentJobQuery,
    uow: AsyncUnitOfWork,
    *,
    capability_enabled: bool = True,
) -> ContentJobDTO:
    """Retrieve content job details by ID with role-based access control."""
    if not capability_enabled:
        raise ForbiddenError("Staff AI capability is disabled")

    async with uow:
        job = await uow.content_jobs.get_by_id(query.job_id)
        if job is None:
            raise EntityNotFoundError(f"Content job '{query.job_id}' not found")

        # Learner is rejected; Teacher/Admin can inspect jobs
        is_staff = any(r in query.user_roles for r in ("teacher", "admin"))
        if not is_staff:
            raise ForbiddenError("Insufficient permissions to view content jobs")

        return to_content_job_dto(job)


async def handle_cancel_content_job(
    cmd: CancelContentJobCommand,
    uow: AsyncUnitOfWork,
    *,
    capability_enabled: bool = True,
) -> ContentJobDTO:
    """Cancel a queued or running content job and release quota if not executed."""
    if not capability_enabled:
        raise ForbiddenError("Staff AI capability is disabled")

    async with uow:
        job = await uow.content_jobs.get_by_id(cmd.job_id)
        if job is None:
            raise EntityNotFoundError(f"Content job '{cmd.job_id}' not found")

        is_admin = "admin" in cmd.user_roles
        if not is_admin and job.created_by != cmd.user_id:
            raise ForbiddenError("Only creator or admin can cancel this job")

        now = datetime.now(UTC)
        was_queued = job.status == ContentJobStatus.QUEUED

        job.cancel(now)
        await uow.content_jobs.update(job)

        # If job was still queued (no provider call started), release reserved budget
        if was_queued:
            reservation = await uow.usage_ledger.get_reservation_by_job_id(job.id)
            if reservation is not None:
                account = await uow.quota.get_by_id(reservation.account_id, for_update=True)
                if account is not None:
                    release_entry = account.release(
                        reservation_entry=reservation,
                        reason=f"job_cancelled_by_{cmd.user_id}",
                    )
                    await uow.quota.save_account(account)
                    await uow.usage_ledger.add_entry(release_entry)

        await uow.commit()
        return to_content_job_dto(job)


async def handle_apply_content_job(
    cmd: ApplyContentJobCommand,
    uow: AsyncUnitOfWork,
    *,
    capability_enabled: bool = True,
) -> ContentJobDTO:
    """Apply generated segments to transcript draft with CAS check."""
    if not capability_enabled:
        raise ForbiddenError("Staff AI capability is disabled")

    async with uow:
        job = await uow.content_jobs.get_by_id(cmd.job_id)
        if job is None:
            raise EntityNotFoundError(f"Content job '{cmd.job_id}' not found")

        if job.status != ContentJobStatus.SUCCEEDED:
            raise InvalidDomainStateError(f"Cannot apply results: job is in status '{job.status.value}'")

        if job.applied_at is not None:
            raise ConflictError("Job results have already been applied")

        # Validate source content version has not drifted
        version = await uow.content.get_by_id(job.content_version_id)
        if version is None or version.is_frozen:
            raise ConflictError("Content version is frozen or does not exist")

        item = await uow.catalog.get_by_id(job.catalog_item_id)
        media_ref = item.media[0] if (item and item.media) else None
        if media_ref is None:
            raise ConflictError("Source media no longer exists")
        _, _, current_source_hash = _job_source_identity(version, media_ref)
        if current_source_hash != job.source_hash:
            raise ConflictError("Source content version was modified during job execution")

        # Determine segments: user overrides or generated draft
        segments = cmd.segments
        if segments is None and job.result_draft:
            raw_segments = job.result_draft.get("segments", [])
            segments = [
                {"scene_id": s["scene_id"], "text_ja": s["text_ja"]}
                for s in raw_segments
                if "scene_id" in s and "text_ja" in s
            ]

        if segments is None:
            segments = []

        # Save transcript draft via existing handler (verifies scenes, length, CAS revision)
        await handle_save_transcript_draft(
            SaveTranscriptDraftCommand(
                user_id=cmd.user_id,
                catalog_item_id=job.catalog_item_id,
                content_version_id=job.content_version_id,
                expected_revision=cmd.expected_revision,
                segments=segments,
                provenance="ai_assisted",
            ),
            uow,
            auto_commit=False,
        )

        now = datetime.now(UTC)
        job.apply(cmd.user_id, now)
        await uow.content_jobs.update(job)
        await uow.commit()

        return to_content_job_dto(job)


async def handle_execute_ai_worker_step(
    uow: AsyncUnitOfWork,
    ai_provider: AiTranscriptionPort,
    *,
    lease_duration_seconds: float = 60.0,
    attempt_token: str | None = None,
    capability_enabled: bool = True,
) -> ContentJobDTO | None:
    """Claim and execute one queued job through the AI provider adapter outside DB transaction."""
    if not capability_enabled:
        return None
    now = datetime.now(UTC)
    token = attempt_token or str(uuid4())

    claimed_job: ContentJob | None = None
    media_key: str = ""
    duration_seconds: int = 300

    # 1. Claim job with row-level lock in a short transaction
    async with uow:
        claimed_job = await uow.content_jobs.claim_next_queued_job(now, lease_duration_seconds, token)
        if claimed_job is None:
            return None

        await uow.catalog.get_by_id(claimed_job.catalog_item_id)
        media_key = claimed_job.provenance.get("source_storage_key", "")
        duration_seconds = claimed_job.provenance.get("source_duration_seconds", 0)
        if not media_key or not duration_seconds:
            claimed_job.record_failure("Source snapshot missing; recreate job after review", retryable=False, now=now)
            await uow.content_jobs.update(claimed_job)
            await uow.commit()
            return to_content_job_dto(claimed_job)
        reservation = await uow.usage_ledger.get_reservation_by_job_id(claimed_job.id)
        await uow.content_jobs.save_attempt(
            AiAttempt(
                id=token,
                job_id=claimed_job.id,
                attempt_number=claimed_job.attempt,
                provider=reservation.provider if reservation else "unknown",
                idempotency_key=f"ai-attempt:{token}",
                state="running",
                lease_expires_at=claimed_job.lease_expires_at,
                created_at=now,
                updated_at=now,
            )
        )
        await uow.commit()

    claimed_attempt = claimed_job.attempt

    # 2. Call AI Provider outside transaction
    provider_error: Exception | None = None
    transcription_result = None
    try:
        transcription_result = await ai_provider.transcribe_and_segment(
            media_storage_key=media_key,
            media_duration_seconds=duration_seconds,
            language=claimed_job.language,
        )
    except TimeoutError as exc:
        provider_error = exc
        logger.warning(
            "ai_job_provider_timeout",
            extra={"job_id": claimed_job.id, "attempt": claimed_job.attempt},
        )
    except Exception as exc:
        provider_error = exc
        logger.error(
            "ai_job_provider_failed",
            extra={"job_id": claimed_job.id, "error_type": type(exc).__name__},
        )

    # 3. Re-enter transaction to record outcome and settle or reconcile usage
    async with uow:
        attempt = await uow.content_jobs.get_attempt(token, for_update=True)
        if attempt is None:
            raise ConflictError("Durable attempt missing; provider result requires reconciliation")
        current_job = await uow.content_jobs.get_by_id(claimed_job.id)
        if current_job is None:
            return None

        res_now = datetime.now(UTC)
        reservation = await uow.usage_ledger.get_reservation_by_job_id(current_job.id)

        # Serialize accounting by quota account, then re-read the detached
        # reservation after acquiring the lock. Late results still owe usage.
        if reservation is not None:
            account = await uow.quota.get_by_id(reservation.account_id, for_update=True)
            reservation = await uow.usage_ledger.get_reservation_by_job_id(current_job.id)
            if account is not None and reservation is not None:
                settlement_key = f"settle:{reservation.idempotency_key}:{claimed_attempt}"
                settled = await uow.usage_ledger.get_by_idempotency_key(
                    account_id=account.id,
                    idempotency_key=settlement_key,
                    kind="settlement",
                )
                if (
                    transcription_result is not None
                    and settled is None
                    and reservation.status in ("reserved", "outcome_unknown")
                ):
                    usage = transcription_result.usage
                    settlement_entry = account.settle(
                        reservation_entry=reservation,
                        actual_audio_seconds=usage.audio_seconds,
                        actual_input_tokens=usage.input_tokens,
                        actual_output_tokens=usage.output_tokens,
                        actual_cost_micros=usage.cost_micros,
                        provider_request_id=usage.provider_request_id,
                        attempt=claimed_attempt,
                        description=f"Settlement for job {current_job.id}",
                        now=res_now,
                    )
                    await uow.quota.save_account(account)
                    await uow.usage_ledger.add_entry(settlement_entry)
                elif provider_error is not None and reservation.status == "reserved":
                    # A generic transport/provider error is not proof of zero
                    # charge. Keep the budget until an operator reconciles it,
                    # including when cancellation revoked result ownership.
                    existing = await uow.usage_ledger.get_by_idempotency_key(
                        account_id=account.id,
                        idempotency_key=f"reconcile:{reservation.idempotency_key}",
                        kind="reconciliation",
                    )
                    if existing is None:
                        entry = account.reconcile(
                            reservation_entry=reservation,
                            status="outcome_unknown",
                            reason="provider_outcome_unknown",
                            now=res_now,
                        )
                        await uow.quota.save_account(account)
                        await uow.usage_ledger.add_entry(entry)

        if transcription_result is not None:
            attempt.provider_request_id = transcription_result.usage.provider_request_id
            attempt.usage = asdict(transcription_result.usage)
            attempt.updated_at = res_now
            if attempt.state == "not_billed":
                # Contradictory late evidence must be visible for investigation.
                attempt.state = "outcome_unknown"
                attempt.evidence = "Late provider usage contradicts operator not-billed decision"
                attempt.resolution_hash = None
            else:
                attempt.state = "settled"
            await uow.content_jobs.save_attempt(attempt)
        elif provider_error is not None:
            await mark_attempt_unknown(attempt, uow, res_now, "Provider error; billing outcome unknown")

        # Lease lost / CAS mismatch guard
        if current_job.attempt_token != token or current_job.status != ContentJobStatus.RUNNING:
            logger.warning(
                "ai_job_lease_lost_or_cancelled",
                extra={
                    "job_id": claimed_job.id,
                    "expected_token": token,
                    "actual_token": current_job.attempt_token,
                    "status": current_job.status,
                },
            )
            # Commit ledger settlement if any occurred, but do not update job draft or status
            await uow.commit()
            return None

        if provider_error is not None:
            reason = "Provider timeout" if isinstance(provider_error, TimeoutError) else "Provider failure"
            current_job.record_failure(
                f"{reason} (outcome unknown; manual reconciliation required)",
                retryable=False,
                now=res_now,
            )
            await uow.content_jobs.update(current_job)
            await uow.commit()
            return to_content_job_dto(current_job)

        # Success path:
        current_job.record_success(
            result_draft={
                "segments": transcription_result.segments,
                "source_hash": current_job.source_hash,
            },
            provenance=transcription_result.provenance,
            now=res_now,
        )
        await uow.content_jobs.update(current_job)
        await uow.commit()
        return to_content_job_dto(current_job)

    return None
