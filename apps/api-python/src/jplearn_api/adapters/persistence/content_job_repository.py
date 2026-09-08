"""SQLAlchemy adapter for ContentJobRepository (ADR-007 PR8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.adapters.persistence.models import ContentJobModel
from jplearn_api.application.ports.repositories import ContentJobRepository
from jplearn_api.domain.content_job import (
    ContentJob,
    ContentJobStatus,
    ContentJobTask,
)


def _to_domain(model: ContentJobModel) -> ContentJob:
    return ContentJob(
        id=model.id,
        catalog_item_id=model.catalog_item_id,
        content_version_id=model.content_version_id,
        task=ContentJobTask(model.task),
        language=model.language,
        status=ContentJobStatus(model.status),
        progress=model.progress,
        provenance=dict(model.provenance) if model.provenance else {},
        source_hash=model.source_hash,
        config_hash=model.config_hash,
        idempotency_key=model.idempotency_key,
        created_by=model.created_by,
        attempt=model.attempt,
        max_attempts=model.max_attempts,
        attempt_token=model.attempt_token,
        lease_expires_at=model.lease_expires_at,
        result_draft=dict(model.result_draft) if model.result_draft else None,
        error_message=model.error_message,
        applied_at=model.applied_at,
        applied_by=model.applied_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


class SqlAlchemyContentJobRepository(ContentJobRepository):
    """SQLAlchemy implementation of ContentJobRepository with skip-locked row claim."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, job: ContentJob) -> None:
        task_str = job.task.value if hasattr(job.task, "value") else str(job.task)
        status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
        model = ContentJobModel(
            id=job.id,
            catalog_item_id=job.catalog_item_id,
            content_version_id=job.content_version_id,
            task=task_str,
            language=job.language,
            status=status_str,
            progress=job.progress,
            provenance=job.provenance,
            source_hash=job.source_hash,
            config_hash=job.config_hash,
            idempotency_key=job.idempotency_key,
            created_by=job.created_by,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            attempt_token=job.attempt_token,
            lease_expires_at=_to_naive(job.lease_expires_at),
            result_draft=job.result_draft,
            error_message=job.error_message,
            applied_at=_to_naive(job.applied_at),
            applied_by=job.applied_by,
            created_at=_to_naive(job.created_at),
            updated_at=_to_naive(job.updated_at),
        )
        self.session.add(model)

    async def get_by_id(self, job_id: str) -> ContentJob | None:
        stmt = select(ContentJobModel).where(ContentJobModel.id == job_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def get_by_idempotency_key(
        self,
        created_by: str,
        idempotency_key: str,
    ) -> ContentJob | None:
        stmt = select(ContentJobModel).where(
            ContentJobModel.created_by == created_by,
            ContentJobModel.idempotency_key == idempotency_key,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_active_job(
        self,
        content_version_id: str,
        task: ContentJobTask,
    ) -> ContentJob | None:
        task_str = task.value if hasattr(task, "value") else str(task)
        stmt = select(ContentJobModel).where(
            ContentJobModel.content_version_id == content_version_id,
            ContentJobModel.task == task_str,
            ContentJobModel.status.in_(["queued", "running"]),
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def claim_next_queued_job(
        self,
        now: datetime,
        lease_duration_seconds: float,
        attempt_token: str,
    ) -> ContentJob | None:
        naive_now = _to_naive(now)
        stmt = (
            select(ContentJobModel)
            .where(
                ContentJobModel.status == "queued",
                ContentJobModel.attempt < ContentJobModel.max_attempts,
            )
            .order_by(ContentJobModel.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        model.status = "running"
        model.attempt += 1
        model.attempt_token = attempt_token
        model.lease_expires_at = _to_naive(now + timedelta(seconds=lease_duration_seconds))
        model.updated_at = naive_now

        return _to_domain(model)

    async def update(self, job: ContentJob) -> None:
        stmt = select(ContentJobModel).where(ContentJobModel.id == job.id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return

        status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
        model.status = status_str
        model.progress = job.progress
        model.provenance = job.provenance
        model.attempt = job.attempt
        model.attempt_token = job.attempt_token
        model.lease_expires_at = _to_naive(job.lease_expires_at)
        model.result_draft = job.result_draft
        model.error_message = job.error_message
        model.applied_at = _to_naive(job.applied_at)
        model.applied_by = job.applied_by
        model.updated_at = _to_naive(job.updated_at)

    async def save_attempt(self, attempt) -> None:
        from dataclasses import asdict
        from jplearn_api.adapters.persistence.models import AiAttemptModel
        values = asdict(attempt)
        for key in ("lease_expires_at", "created_at", "updated_at"):
            values[key] = _to_naive(values[key])
        await self.session.merge(AiAttemptModel(**values))
        await self.session.flush()

    async def get_attempt(self, attempt_id: str, for_update: bool = False):
        from jplearn_api.adapters.persistence.models import AiAttemptModel
        from jplearn_api.domain.ai_attempt import AiAttempt
        stmt = select(AiAttemptModel).where(AiAttemptModel.id == attempt_id).execution_options(populate_existing=True)
        if for_update:
            stmt = stmt.with_for_update()
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return AiAttempt(**{name: getattr(row, name) for name in AiAttempt.__dataclass_fields__})

    async def list_expired_attempts(self, now: datetime, limit: int = 100):
        from jplearn_api.adapters.persistence.models import AiAttemptModel
        stmt = (select(AiAttemptModel.id).where(
            AiAttemptModel.state == "running", AiAttemptModel.lease_expires_at <= _to_naive(now),
        ).order_by(AiAttemptModel.lease_expires_at, AiAttemptModel.id).limit(limit))
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_job_attempts(self, job_id: str):
        from jplearn_api.adapters.persistence.models import AiAttemptModel
        stmt = select(AiAttemptModel.id).where(AiAttemptModel.job_id == job_id).order_by(AiAttemptModel.attempt_number)
        ids = list((await self.session.execute(stmt)).scalars().all())
        return [await self.get_attempt(attempt_id) for attempt_id in ids]
