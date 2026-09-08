"""SQLAlchemy persistence adapters for QuotaAccount and AiUsageLedger (ADR-007 PR8c)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import (
    AiQuotaAccountModel,
    AiUsageLedgerModel,
)
from jplearn_api.domain.quota import (
    AiUsageLedgerEntry,
    QuotaAccount,
)


def _model_to_quota_domain(model: AiQuotaAccountModel) -> QuotaAccount:
    return QuotaAccount(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        max_audio_seconds=model.max_audio_seconds,
        max_input_tokens=model.max_input_tokens,
        max_output_tokens=model.max_output_tokens,
        max_cost_micros=model.max_cost_micros,
        reserved_audio_seconds=model.reserved_audio_seconds,
        reserved_input_tokens=model.reserved_input_tokens,
        reserved_output_tokens=model.reserved_output_tokens,
        reserved_cost_micros=model.reserved_cost_micros,
        used_audio_seconds=model.used_audio_seconds,
        used_input_tokens=model.used_input_tokens,
        used_output_tokens=model.used_output_tokens,
        used_cost_micros=model.used_cost_micros,
        policy_version=model.policy_version,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _model_to_ledger_domain(model: AiUsageLedgerModel) -> AiUsageLedgerEntry:
    return AiUsageLedgerEntry(
        id=model.id,
        account_id=model.account_id,
        job_id=model.job_id,
        user_id=model.user_id,
        idempotency_key=model.idempotency_key,
        kind=model.kind,
        status=model.status,
        provider=model.provider,
        provider_request_id=model.provider_request_id,
        attempt=model.attempt,
        audio_seconds=model.audio_seconds,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        cost_micros=model.cost_micros,
        currency=model.currency,
        policy_version=model.policy_version,
        description=model.description,
        created_at=model.created_at,
        settled_at=model.settled_at,
    )


def _to_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class SqlAlchemyQuotaRepository:
    """SQLAlchemy implementation of QuotaRepository with row-level locking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_account_for_user(
        self,
        user_id: str,
        name: str = "Staff Default Quota",
    ) -> QuotaAccount:
        res = await self.session.execute(select(AiQuotaAccountModel).where(AiQuotaAccountModel.user_id == user_id))
        model = res.scalar_one_or_none()
        if model is not None:
            return _model_to_quota_domain(model)

        # Create new account
        new_id = str(uuid.uuid4())
        model = AiQuotaAccountModel(
            id=new_id,
            user_id=user_id,
            name=name,
            max_audio_seconds=3600,
            max_input_tokens=1000000,
            max_output_tokens=500000,
            max_cost_micros=10000000,  # $10.00
            reserved_audio_seconds=0,
            reserved_input_tokens=0,
            reserved_output_tokens=0,
            reserved_cost_micros=0,
            used_audio_seconds=0,
            used_input_tokens=0,
            used_output_tokens=0,
            used_cost_micros=0,
            policy_version="v1",
            is_active=True,
        )
        self.session.add(model)
        await self.session.flush()
        return _model_to_quota_domain(model)

    async def get_by_id(
        self,
        account_id: str,
        for_update: bool = False,
    ) -> QuotaAccount | None:
        stmt = select(AiQuotaAccountModel).where(AiQuotaAccountModel.id == account_id)
        if for_update:
            stmt = stmt.with_for_update()

        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_quota_domain(model)

    async def save_account(
        self,
        account: QuotaAccount,
    ) -> None:
        res = await self.session.execute(select(AiQuotaAccountModel).where(AiQuotaAccountModel.id == account.id))
        model = res.scalar_one_or_none()
        if model is None:
            model = AiQuotaAccountModel(
                id=account.id,
                user_id=account.user_id,
                name=account.name,
                max_audio_seconds=account.max_audio_seconds,
                max_input_tokens=account.max_input_tokens,
                max_output_tokens=account.max_output_tokens,
                max_cost_micros=account.max_cost_micros,
                reserved_audio_seconds=account.reserved_audio_seconds,
                reserved_input_tokens=account.reserved_input_tokens,
                reserved_output_tokens=account.reserved_output_tokens,
                reserved_cost_micros=account.reserved_cost_micros,
                used_audio_seconds=account.used_audio_seconds,
                used_input_tokens=account.used_input_tokens,
                used_output_tokens=account.used_output_tokens,
                used_cost_micros=account.used_cost_micros,
                policy_version=account.policy_version,
                is_active=account.is_active,
                created_at=_to_naive(account.created_at),
                updated_at=_to_naive(account.updated_at),
            )
            self.session.add(model)
        else:
            model.name = account.name
            model.max_audio_seconds = account.max_audio_seconds
            model.max_input_tokens = account.max_input_tokens
            model.max_output_tokens = account.max_output_tokens
            model.max_cost_micros = account.max_cost_micros
            model.reserved_audio_seconds = account.reserved_audio_seconds
            model.reserved_input_tokens = account.reserved_input_tokens
            model.reserved_output_tokens = account.reserved_output_tokens
            model.reserved_cost_micros = account.reserved_cost_micros
            model.used_audio_seconds = account.used_audio_seconds
            model.used_input_tokens = account.used_input_tokens
            model.used_output_tokens = account.used_output_tokens
            model.used_cost_micros = account.used_cost_micros
            model.policy_version = account.policy_version
            model.is_active = account.is_active
            model.updated_at = _to_naive(account.updated_at)

        await self.session.flush()


class SqlAlchemyUsageLedgerRepository:
    """SQLAlchemy implementation of UsageLedgerRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_entry(
        self,
        entry: AiUsageLedgerEntry,
    ) -> None:
        # Domain reservations are detached values. Persist their transition in
        # the same transaction as the appended outcome and account counters.
        if entry.kind in ("settlement", "release", "reconciliation"):
            source_key = entry.idempotency_key.split(":", 1)[1]
            if entry.kind == "settlement":
                source_key = source_key.rsplit(":", 1)[0]
            result = await self.session.execute(
                select(AiUsageLedgerModel)
                .where(
                    AiUsageLedgerModel.account_id == entry.account_id,
                    AiUsageLedgerModel.idempotency_key == source_key,
                    AiUsageLedgerModel.kind == "reservation",
                )
                .with_for_update()
            )
            reservation = result.scalar_one_or_none()
            if reservation is not None:
                reservation.status = entry.status
                reservation.settled_at = _to_naive(entry.settled_at)
        model = AiUsageLedgerModel(
            id=entry.id,
            account_id=entry.account_id,
            job_id=entry.job_id,
            user_id=entry.user_id,
            idempotency_key=entry.idempotency_key,
            kind=entry.kind,
            status=entry.status,
            provider=entry.provider,
            provider_request_id=entry.provider_request_id,
            attempt=entry.attempt,
            audio_seconds=entry.audio_seconds,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            cost_micros=entry.cost_micros,
            currency=entry.currency,
            policy_version=entry.policy_version,
            description=entry.description,
            created_at=_to_naive(entry.created_at),
            settled_at=_to_naive(entry.settled_at),
        )
        self.session.add(model)
        await self.session.flush()

    async def get_entry_by_id(
        self,
        entry_id: str,
    ) -> AiUsageLedgerEntry | None:
        res = await self.session.execute(select(AiUsageLedgerModel).where(AiUsageLedgerModel.id == entry_id))
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_ledger_domain(model)

    async def get_by_idempotency_key(
        self,
        account_id: str,
        idempotency_key: str,
        kind: str,
    ) -> AiUsageLedgerEntry | None:
        res = await self.session.execute(
            select(AiUsageLedgerModel).where(
                AiUsageLedgerModel.account_id == account_id,
                AiUsageLedgerModel.idempotency_key == idempotency_key,
                AiUsageLedgerModel.kind == kind,
            )
        )
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_ledger_domain(model)

    async def get_reservation_by_job_id(
        self,
        job_id: str,
    ) -> AiUsageLedgerEntry | None:
        res = await self.session.execute(
            select(AiUsageLedgerModel)
            .execution_options(populate_existing=True)
            .where(
                AiUsageLedgerModel.job_id == job_id,
                AiUsageLedgerModel.kind == "reservation",
            )
        )
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_ledger_domain(model)

    async def get_settlement(
        self,
        provider: str,
        provider_request_id: str,
        attempt: int,
        kind: str = "settlement",
    ) -> AiUsageLedgerEntry | None:
        res = await self.session.execute(
            select(AiUsageLedgerModel).where(
                AiUsageLedgerModel.provider == provider,
                AiUsageLedgerModel.provider_request_id == provider_request_id,
                AiUsageLedgerModel.attempt == attempt,
                AiUsageLedgerModel.kind == kind,
            )
        )
        model = res.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_ledger_domain(model)

    async def list_user_usage(
        self,
        user_id: str,
        from_date: datetime,
        to_date: datetime,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AiUsageLedgerEntry], int]:
        base_where = [
            AiUsageLedgerModel.user_id == user_id,
            AiUsageLedgerModel.created_at >= from_date,
            AiUsageLedgerModel.created_at <= to_date,
        ]

        # Total count
        count_stmt = select(func.count(AiUsageLedgerModel.id)).where(*base_where)
        count_res = await self.session.execute(count_stmt)
        total = count_res.scalar_one() or 0

        # Items page
        items_stmt = (
            select(AiUsageLedgerModel)
            .where(*base_where)
            .order_by(AiUsageLedgerModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items_res = await self.session.execute(items_stmt)
        models = items_res.scalars().all()
        return [_model_to_ledger_domain(m) for m in models], total

    async def get_summary(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        date_expr = func.to_char(AiUsageLedgerModel.created_at, "YYYY-MM-DD").label("date")
        stmt = (
            select(
                AiUsageLedgerModel.provider,
                AiUsageLedgerModel.currency,
                date_expr,
                func.sum(AiUsageLedgerModel.audio_seconds).label("total_audio"),
                func.sum(AiUsageLedgerModel.input_tokens).label("total_input"),
                func.sum(AiUsageLedgerModel.output_tokens).label("total_output"),
                func.sum(AiUsageLedgerModel.cost_micros).label("total_cost"),
                func.count(AiUsageLedgerModel.id).label("events_count"),
            )
            .where(
                AiUsageLedgerModel.created_at >= from_date,
                AiUsageLedgerModel.created_at <= to_date,
                AiUsageLedgerModel.kind == "settlement",
            )
            .group_by(
                AiUsageLedgerModel.provider,
                AiUsageLedgerModel.currency,
                date_expr,
            )
            .order_by(date_expr.desc(), AiUsageLedgerModel.provider)
        )
        res = await self.session.execute(stmt)
        rows = res.all()

        return [
            {
                "provider": r.provider,
                "currency": r.currency,
                "date": r.date,
                "total_audio_seconds": int(r.total_audio or 0),
                "total_input_tokens": int(r.total_input or 0),
                "total_output_tokens": int(r.total_output or 0),
                "total_cost_micros": int(r.total_cost or 0),
                "events_count": int(r.events_count or 0),
            }
            for r in rows
        ]
