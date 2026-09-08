"""Application handlers for AI Quota Accounts and Usage Ledger (ADR-007 PR8c)."""

from __future__ import annotations

from jplearn_api.application.commands import (
    ReconcileQuotaCommand,
    ReleaseQuotaCommand,
    ReserveQuotaCommand,
    SettleUsageCommand,
)
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import (
    GetAiUsageSummaryQuery,
    GetMyAiUsageQuery,
)
from jplearn_api.application.read_models import (
    AiUsageItemDTO,
    AiUsageListDTO,
    AiUsageSummaryDTO,
    AiUsageSummaryItemDTO,
)
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    ForbiddenError,
    ValidationError,
)
from jplearn_api.domain.quota import AiUsageLedgerEntry


async def handle_reserve_quota(
    cmd: ReserveQuotaCommand,
    uow: AsyncUnitOfWork,
    *,
    auto_commit: bool = True,
) -> AiUsageLedgerEntry:
    """Reserve AI quota for a job under row-level lock with idempotency."""
    async with uow:
        if cmd.account_id:
            account = await uow.quota.get_by_id(cmd.account_id, for_update=True)
            if account is None:
                raise EntityNotFoundError(f"Quota account '{cmd.account_id}' not found")
        else:
            account = await uow.quota.get_or_create_account_for_user(cmd.user_id)
            # Re-fetch with lock for concurrent safety
            account = await uow.quota.get_by_id(account.id, for_update=True) or account

        # Check idempotency: if reservation already exists, return it
        existing = await uow.usage_ledger.get_by_idempotency_key(
            account_id=account.id,
            idempotency_key=cmd.idempotency_key,
            kind="reservation",
        )
        if existing is not None:
            return existing

        # Reserve quota
        entry = account.reserve(
            job_id=cmd.job_id,
            user_id=cmd.user_id,
            idempotency_key=cmd.idempotency_key,
            provider=cmd.provider,
            audio_seconds=cmd.audio_seconds,
            input_tokens=cmd.input_tokens,
            output_tokens=cmd.output_tokens,
            cost_micros=cmd.cost_micros,
            currency=cmd.currency,
            description=cmd.description,
        )

        await uow.quota.save_account(account)
        await uow.usage_ledger.add_entry(entry)
        if auto_commit:
            await uow.commit()
        return entry


async def handle_settle_usage(
    cmd: SettleUsageCommand,
    uow: AsyncUnitOfWork,
) -> AiUsageLedgerEntry:
    """Settle actual AI resource usage and release unused reservation."""
    async with uow:
        account = await uow.quota.get_by_id(cmd.account_id, for_update=True)
        if account is None:
            raise EntityNotFoundError(f"Quota account '{cmd.account_id}' not found")

        reservation = await uow.usage_ledger.get_entry_by_id(cmd.reservation_entry_id)
        if reservation is None:
            raise EntityNotFoundError(f"Reservation '{cmd.reservation_entry_id}' not found")

        # Check idempotency tuple if provider_request_id provided
        if cmd.provider_request_id:
            existing_settlement = await uow.usage_ledger.get_settlement(
                provider=reservation.provider,
                provider_request_id=cmd.provider_request_id,
                attempt=cmd.attempt,
                kind="settlement",
            )
            if existing_settlement is not None:
                return existing_settlement

        settlement_entry = account.settle(
            reservation_entry=reservation,
            actual_audio_seconds=cmd.actual_audio_seconds,
            actual_input_tokens=cmd.actual_input_tokens,
            actual_output_tokens=cmd.actual_output_tokens,
            actual_cost_micros=cmd.actual_cost_micros,
            provider_request_id=cmd.provider_request_id,
            attempt=cmd.attempt,
            description=cmd.description,
        )

        await uow.quota.save_account(account)
        await uow.usage_ledger.add_entry(settlement_entry)
        await uow.commit()
        return settlement_entry


async def handle_release_quota(
    cmd: ReleaseQuotaCommand,
    uow: AsyncUnitOfWork,
) -> AiUsageLedgerEntry:
    """Release unbilled reservation back to available quota."""
    async with uow:
        account = await uow.quota.get_by_id(cmd.account_id, for_update=True)
        if account is None:
            raise EntityNotFoundError(f"Quota account '{cmd.account_id}' not found")

        reservation = await uow.usage_ledger.get_entry_by_id(cmd.reservation_entry_id)
        if reservation is None:
            raise EntityNotFoundError(f"Reservation '{cmd.reservation_entry_id}' not found")

        release_entry = account.release(
            reservation_entry=reservation,
            reason=cmd.reason,
        )

        await uow.quota.save_account(account)
        await uow.usage_ledger.add_entry(release_entry)
        await uow.commit()
        return release_entry


async def handle_reconcile_quota(
    cmd: ReconcileQuotaCommand,
    uow: AsyncUnitOfWork,
) -> AiUsageLedgerEntry:
    """Reconcile reservation when provider outcome is unknown or audit completed."""
    async with uow:
        account = await uow.quota.get_by_id(cmd.account_id, for_update=True)
        if account is None:
            raise EntityNotFoundError(f"Quota account '{cmd.account_id}' not found")

        reservation = await uow.usage_ledger.get_entry_by_id(cmd.reservation_entry_id)
        if reservation is None:
            raise EntityNotFoundError(f"Reservation '{cmd.reservation_entry_id}' not found")

        reconcile_entry = account.reconcile(
            reservation_entry=reservation,
            status=cmd.status,
            reason=cmd.reason,
        )

        await uow.quota.save_account(account)
        await uow.usage_ledger.add_entry(reconcile_entry)
        await uow.commit()
        return reconcile_entry


async def handle_get_my_ai_usage(
    query: GetMyAiUsageQuery,
    uow: AsyncUnitOfWork,
    capability_enabled: bool = True,
) -> AiUsageListDTO:
    """List staff AI usage entries within date range (max 90 days)."""
    if not capability_enabled:
        raise ForbiddenError("AI usage tracking is currently disabled")

    if query.from_date > query.to_date:
        raise ValidationError("from_date must be before or equal to to_date")

    delta = query.to_date - query.from_date
    if delta.total_seconds() > 90 * 86400:
        raise ValidationError("Date range must not exceed 90 days")

    async with uow:
        entries, total = await uow.usage_ledger.list_user_usage(
            user_id=query.user_id,
            from_date=query.from_date,
            to_date=query.to_date,
            limit=query.limit,
            offset=query.offset,
        )

        items = [
            AiUsageItemDTO(
                id=e.id,
                account_id=e.account_id,
                job_id=e.job_id,
                kind=e.kind,
                status=e.status,
                provider=e.provider,
                provider_request_id=e.provider_request_id,
                attempt=e.attempt,
                audio_seconds=e.audio_seconds,
                input_tokens=e.input_tokens,
                output_tokens=e.output_tokens,
                cost_micros=e.cost_micros,
                currency=e.currency,
                policy_version=e.policy_version,
                created_at=e.created_at,
                settled_at=e.settled_at,
                description=e.description,
            )
            for e in entries
        ]

        return AiUsageListDTO(
            items=items,
            total_count=total,
            from_date=query.from_date,
            to_date=query.to_date,
        )


async def handle_get_ai_usage_summary(
    query: GetAiUsageSummaryQuery,
    uow: AsyncUnitOfWork,
    capability_enabled: bool = True,
) -> AiUsageSummaryDTO:
    """Admin summary of AI usage across all accounts within date range (max 90 days)."""
    if not capability_enabled:
        raise ForbiddenError("AI usage tracking is currently disabled")

    if query.from_date > query.to_date:
        raise ValidationError("from_date must be before or equal to to_date")

    delta = query.to_date - query.from_date
    if delta.total_seconds() > 90 * 86400:
        raise ValidationError("Date range must not exceed 90 days")

    async with uow:
        raw_summary = await uow.usage_ledger.get_summary(
            from_date=query.from_date,
            to_date=query.to_date,
        )

        summary_items: list[AiUsageSummaryItemDTO] = []
        total_audio = 0
        total_input = 0
        total_output = 0
        total_cost = 0

        for row in raw_summary:
            item = AiUsageSummaryItemDTO(
                provider=row["provider"],
                currency=row["currency"],
                date=row["date"],
                total_audio_seconds=row["total_audio_seconds"],
                total_input_tokens=row["total_input_tokens"],
                total_output_tokens=row["total_output_tokens"],
                total_cost_micros=row["total_cost_micros"],
                events_count=row["events_count"],
            )
            summary_items.append(item)
            total_audio += row["total_audio_seconds"]
            total_input += row["total_input_tokens"]
            total_output += row["total_output_tokens"]
            total_cost += row["total_cost_micros"]

        return AiUsageSummaryDTO(
            from_date=query.from_date,
            to_date=query.to_date,
            summary=summary_items,
            total_audio_seconds=total_audio,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_micros=total_cost,
        )
