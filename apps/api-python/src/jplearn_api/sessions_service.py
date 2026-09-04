from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.datetime_adapt import to_json_z, to_naive_utc
from jplearn_api.models import Device, LearnerProgress, LearningEvent, LearningSession
from jplearn_api.schemas import LearnerProgressPublic, LearningSessionPublic

ZOMBIE_SESSION_SECONDS = 4 * 60 * 60


def minutes_from_duration(duration_seconds: int) -> int:
    if duration_seconds > ZOMBIE_SESSION_SECONDS or duration_seconds < 0:
        return 0
    return duration_seconds // 60


def _now_naive() -> datetime:
    return to_naive_utc(datetime.now(UTC))


async def _record_event(
    session: AsyncSession,
    user_id: str,
    event_type: str,
    payload: dict,
    session_id: str | None,
) -> None:
    session.add(
        LearningEvent(
            id=str(uuid4()),
            user_id=user_id,
            session_id=session_id,
            type=event_type,
            payload=payload,
            created_at=_now_naive(),
        ),
    )


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
    progress = await session.get(LearnerProgress, user_id)
    if progress is None:
        raise HTTPException(status_code=500, detail="Missing learner progress")
    await _record_event(session, user_id, "session_started", {}, learning.id)
    await session.flush()
    await _record_event(session, user_id, "level_exposed", {"ci_level": progress.current_ci_level}, learning.id)
    await session.commit()
    return to_public(learning)


async def progress(session: AsyncSession, user_id: str) -> LearnerProgressPublic:
    row = await session.get(LearnerProgress, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Progress not found")
    return LearnerProgressPublic(
        minutes_comprehensible=row.minutes_comprehensible,
        current_ci_level=row.current_ci_level,
    )


async def end(session: AsyncSession, user_id: str, session_id: str) -> LearnerProgressPublic:
    learning = await session.get(LearningSession, session_id)
    if learning is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if learning.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    # ADR-003 D10 KNOWN_DEBT_CARRIED: ended_at is read outside the transaction.
    # Concurrent end() can increment minutes twice. Do not "fix" only in Python.
    if learning.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session already ended")

    ended_at = _now_naive()
    duration = int((ended_at - learning.started_at).total_seconds())
    minutes = minutes_from_duration(duration)
    learning.ended_at = ended_at
    learning.duration_seconds = duration
    row = await session.get(LearnerProgress, learning.user_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Missing learner progress")
    row.minutes_comprehensible += minutes
    row.updated_at = ended_at
    await _record_event(session, user_id, "session_ended", {}, learning.id)
    await session.flush()
    await _record_event(session, user_id, "minutes_comprehensible", {"minutes": minutes}, learning.id)
    await session.commit()
    return await progress(session, user_id)
