"""Conservative attempt expiry and auditable, administrator-only reconciliation."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json

from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.domain.errors import ConflictError, EntityNotFoundError, ForbiddenError, ValidationError


async def mark_attempt_unknown(attempt, uow, now, reason):
    """Caller holds attempt lock; retain budget and add one reconciliation event."""
    reservation = await uow.usage_ledger.get_reservation_by_job_id(attempt.job_id)
    if reservation is not None:
        account = await uow.quota.get_by_id(reservation.account_id, for_update=True)
        reservation = await uow.usage_ledger.get_reservation_by_job_id(attempt.job_id)
        if account is not None and reservation.status == "reserved":
            existing = await uow.usage_ledger.get_by_idempotency_key(
                account_id=account.id,
                idempotency_key=f"reconcile:{reservation.idempotency_key}", kind="reconciliation",
            )
            if existing is None:
                entry = account.reconcile(reservation, "outcome_unknown", now=now, reason=reason)
                await uow.quota.save_account(account)
                await uow.usage_ledger.add_entry(entry)
    attempt.state = "outcome_unknown"
    attempt.evidence = reason
    attempt.updated_at = now
    await uow.content_jobs.save_attempt(attempt)


async def sweep_expired_ai_attempts(uow: AsyncUnitOfWork, *, now=None, limit=100) -> int:
    """Expire bounded batches without calling a provider or requeueing work."""
    now = now or datetime.now(timezone.utc)
    if not 1 <= limit <= 1000:
        raise ValidationError("limit must be between 1 and 1000")
    async with uow:
        ids = await uow.content_jobs.list_expired_attempts(now, limit)
    count = 0
    for attempt_id in ids:
        async with uow:
            attempt = await uow.content_jobs.get_attempt(attempt_id, for_update=True)
            if attempt is None or attempt.state != "running":
                continue
            expiry = attempt.lease_expires_at.replace(tzinfo=timezone.utc)
            if expiry > now:
                continue
            await mark_attempt_unknown(attempt, uow, now, "Lease expired; provider outcome requires operator evidence")
            job = await uow.content_jobs.get_by_id(attempt.job_id)
            if job is not None and job.attempt_token == attempt.id and job.status.value == "running":
                job.record_failure("Provider outcome unknown after lease expiry; reconcile attempt", retryable=False, now=now)
                await uow.content_jobs.update(job)
            await uow.commit()
            count += 1
    return count


async def reconcile_ai_attempt(
    uow: AsyncUnitOfWork, *, job_id: str, attempt_id: str, user_id: str,
    user_roles: tuple[str, ...], decision: str, evidence: str,
    provider_request_id: str | None = None, usage: dict | None = None,
):
    """Finalize unknown usage once; conflicting repeated decisions return 409."""
    if "admin" not in user_roles:
        raise ForbiddenError("Only an admin can reconcile provider billing")
    if decision not in ("billed", "not_billed") or not evidence or not 10 <= len(evidence.strip()) <= 2000:
        raise ValidationError("decision and 10–2000 characters of provider evidence are required")
    usage = usage or {}
    units = ("audio_seconds", "input_tokens", "output_tokens", "cost_micros")
    if decision == "billed":
        if not provider_request_id or not all(type(usage.get(k)) is int and 0 <= usage[k] <= 2**31-1 for k in units):
            raise ValidationError("Billed outcome requires provider request ID and bounded nonnegative usage")
        if usage.get("currency") != "USD":
            raise ValidationError("Current quota policy supports USD only")
    elif usage or provider_request_id:
        raise ValidationError("not_billed must omit usage and provider request ID")
    payload_hash = hashlib.sha256(json.dumps({
        "decision": decision, "evidence": evidence.strip(), "provider_request_id": provider_request_id, "usage": usage,
    }, sort_keys=True).encode()).hexdigest()
    async with uow:
        attempt = await uow.content_jobs.get_attempt(attempt_id, for_update=True)
        if attempt is None or attempt.job_id != job_id:
            raise EntityNotFoundError("Attempt not found for job")
        if attempt.resolution_hash:
            if attempt.resolution_hash != payload_hash:
                raise ConflictError("Attempt already reconciled with different evidence or usage")
            return attempt
        if attempt.state != "outcome_unknown":
            raise ConflictError("Only unknown attempts may be reconciled")
        reservation = await uow.usage_ledger.get_reservation_by_job_id(job_id)
        if reservation is None:
            raise ConflictError("Missing reservation; accounting investigation required")
        account = await uow.quota.get_by_id(reservation.account_id, for_update=True)
        reservation = await uow.usage_ledger.get_reservation_by_job_id(job_id)
        if account is None or reservation.status not in ("reserved", "outcome_unknown"):
            raise ConflictError("Reservation was already finalized")
        now = datetime.now(timezone.utc)
        if decision == "billed":
            entry = account.settle(
                reservation, *(usage[k] for k in units),
                provider_request_id=provider_request_id, attempt=attempt.attempt_number,
                now=now, description="Operator confirmed billed usage",
            )
            attempt.state = "settled"
            attempt.usage = usage
            attempt.provider_request_id = provider_request_id
        else:
            # Definitive operator evidence establishes that this unknown call
            # was not billed, so release is now safe.
            reservation.status = "reserved"
            entry = account.release(reservation, now=now, reason="Operator confirmed not billed")
            attempt.state = "not_billed"
        await uow.quota.save_account(account)
        await uow.usage_ledger.add_entry(entry)
        attempt.resolved_by = user_id
        attempt.evidence = evidence.strip()
        attempt.resolution_hash = payload_hash
        attempt.updated_at = now
        await uow.content_jobs.save_attempt(attempt)
        await uow.commit()
        return attempt
