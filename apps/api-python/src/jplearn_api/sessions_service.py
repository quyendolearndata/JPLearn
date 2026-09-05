from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.datetime_adapt import to_json_z, to_naive_utc
from jplearn_api.models import Device, LearnerProgress, LearningEvent, LearningSession
from jplearn_api.schemas import LearnerProgressPublic, LearningSessionPublic
from jplearn_api.session_policy import (
    ForbiddenSession,
    LearnerProgressNotFound,
    SessionAlreadyEnded,
    SessionNotFound,
    minutes_from_duration,
)


def _now_naive() -> datetime:
    return to_naive_utc(datetime.now(UTC))


def to_public(session: LearningSession) -> LearningSessionPublic:
    return LearningSessionPublic(
        id=session.id,
        device_class=session.device_class,
        started_at=to_json_z(session.started_at),
        ended_at=to_json_z(session.ended_at) if session.ended_at else None,
        duration_seconds=session.duration_seconds,
    )


async def start(session: AsyncSession, user_id: str, device_class: str) -> LearningSessionPublic:
    started_at = _now_naive()
    try:
        learning = LearningSession(
            id=str(uuid4()),
            user_id=user_id,
            device_class=device_class,
            started_at=started_at,
        )
        session.add(learning)
        await session.flush()

        stmt = insert(Device).values(
            id=str(uuid4()),
            user_id=user_id,
            device_class=device_class,
            last_seen_at=started_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "device_class"],
            set_={"last_seen_at": started_at},
        )
        await session.execute(stmt)

        progress_row = await session.get(LearnerProgress, user_id)
        if progress_row is None:
            raise LearnerProgressNotFound("Missing learner progress")

        session.add(
            LearningEvent(
                id=str(uuid4()),
                user_id=user_id,
                session_id=learning.id,
                type="session_started",
                payload={},
                created_at=started_at,
            )
        )
        await session.flush()
        session.add(
            LearningEvent(
                id=str(uuid4()),
                user_id=user_id,
                session_id=learning.id,
                type="level_exposed",
                payload={"ci_level": progress_row.current_ci_level},
                created_at=_now_naive(),
            )
        )
        await session.commit()
        return to_public(learning)
    except Exception:
        await session.rollback()
        raise


async def progress(session: AsyncSession, user_id: str) -> LearnerProgressPublic:
    row = await session.get(LearnerProgress, user_id)
    if row is None:
        raise LearnerProgressNotFound("Progress not found")
    return LearnerProgressPublic(
        minutes_comprehensible=row.minutes_comprehensible,
        current_ci_level=row.current_ci_level,
    )


async def end(session: AsyncSession, user_id: str, session_id: str) -> LearnerProgressPublic:
    """Exactly-once session termination with row locking on PostgreSQL.

    Locks session row and learner_progress row in the same transaction to guarantee
    no lost updates even when multiple sessions for the same user end concurrently.
    Explicit commit on success and rollback on any failure.
    """
    try:
        # 1. Lock and load session
        stmt = select(LearningSession).where(LearningSession.id == session_id).with_for_update()
        result = await session.execute(stmt)
        learning = result.scalar_one_or_none()
        if learning is None:
            raise SessionNotFound("Session not found")
        if learning.user_id != user_id:
            raise ForbiddenSession("Forbidden")

        # 2. Guard against duplicate termination under lock
        if learning.ended_at is not None:
            raise SessionAlreadyEnded("Session already ended")

        ended_at = _now_naive()
        duration = int((ended_at - learning.started_at).total_seconds())
        minutes = minutes_from_duration(duration)
        learning.ended_at = ended_at
        learning.duration_seconds = duration

        # 3. Lock user progress row to prevent concurrent lost updates
        stmt_prog = select(LearnerProgress).where(LearnerProgress.user_id == user_id).with_for_update()
        result_prog = await session.execute(stmt_prog)
        progress_row = result_prog.scalar_one_or_none()
        if progress_row is None:
            raise LearnerProgressNotFound("Missing learner progress")

        # 4. Apply updates
        progress_row.minutes_comprehensible += minutes
        progress_row.updated_at = ended_at

        # 5. Emit exactly one session_ended and one minutes_comprehensible event
        session.add(
            LearningEvent(
                id=str(uuid4()),
                user_id=user_id,
                session_id=learning.id,
                type="session_ended",
                payload={},
                created_at=ended_at,
            )
        )
        session.add(
            LearningEvent(
                id=str(uuid4()),
                user_id=user_id,
                session_id=learning.id,
                type="minutes_comprehensible",
                payload={"minutes": minutes},
                created_at=ended_at,
            )
        )

        await session.commit()
        return LearnerProgressPublic(
            minutes_comprehensible=progress_row.minutes_comprehensible,
            current_ci_level=progress_row.current_ci_level,
        )
    except Exception:
        await session.rollback()
        raise

