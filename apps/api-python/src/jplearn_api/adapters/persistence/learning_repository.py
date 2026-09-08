"""SQLAlchemy implementation of LearningRepository with pessimistic row locking."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.ports.repositories import LearningRepository
from jplearn_api.domain.learning import (
    LearnerProgress as DomainLearnerProgress,
    LearningSession as DomainLearningSession,
)
from jplearn_api.adapters.persistence.models import (
    Device,
    LearnerProgress as OrmLearnerProgress,
    LearningEvent as OrmLearningEvent,
    LearningSession as OrmLearningSession,
)


class SqlAlchemyLearningRepository(LearningRepository):
    """PostgreSQL/SQLAlchemy implementation of LearningRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, session: DomainLearningSession) -> None:
        orm_session = OrmLearningSession(
            id=session.id,
            user_id=session.user_id,
            device_class=session.device_class,
            started_at=session.started_at,
            ended_at=session.ended_at,
            duration_seconds=session.duration_seconds,
        )
        self._session.add(orm_session)
        await self._session.flush()

    async def get_session(self, session_id: str) -> DomainLearningSession | None:
        result = await self._session.execute(
            select(OrmLearningSession).where(OrmLearningSession.id == session_id),
        )
        orm_session = result.scalar_one_or_none()
        if orm_session is None:
            return None
        return DomainLearningSession(
            id=orm_session.id,
            user_id=orm_session.user_id,
            device_class=orm_session.device_class,
            started_at=orm_session.started_at,
            ended_at=orm_session.ended_at,
            duration_seconds=orm_session.duration_seconds,
        )

    async def lock_and_get_session(self, session_id: str) -> DomainLearningSession | None:
        stmt = (
            select(OrmLearningSession)
            .where(OrmLearningSession.id == session_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm_session = result.scalar_one_or_none()
        if orm_session is None:
            return None
        return DomainLearningSession(
            id=orm_session.id,
            user_id=orm_session.user_id,
            device_class=orm_session.device_class,
            started_at=orm_session.started_at,
            ended_at=orm_session.ended_at,
            duration_seconds=orm_session.duration_seconds,
        )

    async def acquire_idempotency_lock(self, user_id: str, key: str) -> None:
        """Acquire a transaction-scoped advisory lock for (user_id, idempotency_key)."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:user_id), hashtext(:key))"),
            {"user_id": user_id, "key": key},
        )

    async def get_idempotency_session(self, user_id: str, key: str) -> tuple[str, str] | None:
        from jplearn_api.adapters.persistence.models import SessionIdempotencyKey
        stmt = select(SessionIdempotencyKey).where(
            SessionIdempotencyKey.user_id == user_id,
            SessionIdempotencyKey.key == key,
        )
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return (record.session_id, record.request_hash)

    async def save_idempotency(self, user_id: str, key: str, session_id: str, request_hash: str) -> None:
        from jplearn_api.adapters.persistence.models import SessionIdempotencyKey
        record = SessionIdempotencyKey(
            user_id=user_id,
            key=key,
            session_id=session_id,
            request_hash=request_hash,
        )
        self._session.add(record)
        await self._session.flush()

    async def update_session(self, session: DomainLearningSession) -> None:

        result = await self._session.execute(
            select(OrmLearningSession).where(OrmLearningSession.id == session.id),
        )
        orm_session = result.scalar_one_or_none()
        if orm_session is not None:
            orm_session.ended_at = session.ended_at
            orm_session.duration_seconds = session.duration_seconds
            await self._session.flush()

    async def upsert_device(self, user_id: str, device_class: str, last_seen_at: datetime) -> None:
        stmt = insert(Device).values(
            id=str(uuid4()),
            user_id=user_id,
            device_class=device_class,
            last_seen_at=last_seen_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "device_class"],
            set_={"last_seen_at": last_seen_at},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_progress(self, user_id: str) -> DomainLearnerProgress | None:
        orm_prog = await self._session.get(OrmLearnerProgress, user_id)
        if orm_prog is None:
            return None
        return DomainLearnerProgress(
            user_id=orm_prog.user_id,
            minutes_comprehensible=orm_prog.minutes_comprehensible,
            current_ci_level=orm_prog.current_ci_level,
            updated_at=orm_prog.updated_at,
        )

    async def lock_and_get_progress(self, user_id: str) -> DomainLearnerProgress | None:
        stmt = (
            select(OrmLearnerProgress)
            .where(OrmLearnerProgress.user_id == user_id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        orm_prog = result.scalar_one_or_none()
        if orm_prog is None:
            return None
        return DomainLearnerProgress(
            user_id=orm_prog.user_id,
            minutes_comprehensible=orm_prog.minutes_comprehensible,
            current_ci_level=orm_prog.current_ci_level,
            updated_at=orm_prog.updated_at,
        )

    async def update_progress(self, progress: DomainLearnerProgress) -> None:
        result = await self._session.execute(
            select(OrmLearnerProgress).where(OrmLearnerProgress.user_id == progress.user_id),
        )
        orm_prog = result.scalar_one_or_none()
        if orm_prog is not None:
            orm_prog.minutes_comprehensible = progress.minutes_comprehensible
            orm_prog.updated_at = progress.updated_at
            await self._session.flush()

    async def record_event(
        self,
        user_id: str,
        session_id: str | None,
        event_type: str,
        payload: dict,
        created_at: datetime,
    ) -> None:
        self._session.add(
            OrmLearningEvent(
                id=str(uuid4()),
                user_id=user_id,
                session_id=session_id,
                type=event_type,
                payload=payload,
                created_at=created_at,
            )
        )
        await self._session.flush()
