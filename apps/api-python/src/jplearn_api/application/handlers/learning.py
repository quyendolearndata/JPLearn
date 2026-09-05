"""Learning sessions and progress use case handlers (Pure Python)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from jplearn_api.application.commands import EndLearningSessionCommand, StartLearningSessionCommand
from jplearn_api.application.ports.repositories import LearningRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import GetLearnerProgressQuery
from jplearn_api.application.read_models import LearnerProgressDTO, LearningSessionDTO
from jplearn_api.domain.errors import EntityNotFoundError, ForbiddenError
from jplearn_api.domain.learning import LearningSession, minutes_from_duration


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def handle_start_session(
    cmd: StartLearningSessionCommand,
    uow: AsyncUnitOfWork,
    *,
    clock: Callable[[], datetime] = _now_naive,
    id_generator: Callable[[], str] = lambda: str(uuid4()),
) -> LearningSessionDTO:
    """Start a learning session, update device last seen, and emit events atomically."""
    started_at = clock()
    session = LearningSession(
        id=id_generator(),
        user_id=cmd.user_id,
        device_class=cmd.device_class,
        started_at=started_at,
    )

    async with uow:
        await uow.learning.create_session(session)
        await uow.learning.upsert_device(cmd.user_id, cmd.device_class, started_at)

        progress = await uow.learning.get_progress(cmd.user_id)
        if progress is None:
            raise EntityNotFoundError("Missing learner progress")

        await uow.learning.record_event(cmd.user_id, session.id, "session_started", {}, started_at)
        await uow.learning.record_event(
            cmd.user_id,
            session.id,
            "level_exposed",
            {"ci_level": progress.current_ci_level},
            clock(),
        )
        await uow.commit()

    return LearningSessionDTO(
        id=session.id,
        device_class=session.device_class,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=session.duration_seconds,
    )


async def handle_end_session(
    cmd: EndLearningSessionCommand,
    uow: AsyncUnitOfWork,
    *,
    clock: Callable[[], datetime] = _now_naive,
) -> LearnerProgressDTO:
    """End a learning session exactly-once with pessimistic row locking and atomic progress/event update."""
    async with uow:
        # 1. Lock and load session
        session = await uow.learning.lock_and_get_session(cmd.session_id)
        if session is None:
            raise EntityNotFoundError("Session not found")
        if session.user_id != cmd.user_id:
            raise ForbiddenError("Forbidden")

        # 2. Guard against duplicate termination under lock (domain method raises SessionAlreadyEndedError)
        ended_at = clock()
        duration = session.end(ended_at)
        minutes = minutes_from_duration(duration)
        await uow.learning.update_session(session)

        # 3. Lock user progress row to prevent concurrent lost updates
        progress = await uow.learning.lock_and_get_progress(cmd.user_id)
        if progress is None:
            raise EntityNotFoundError("Missing learner progress")

        progress.add_minutes(minutes, ended_at)
        await uow.learning.update_progress(progress)

        # 4. Emit exactly one session_ended and one minutes_comprehensible event
        await uow.learning.record_event(cmd.user_id, session.id, "session_ended", {}, ended_at)
        await uow.learning.record_event(
            cmd.user_id,
            session.id,
            "minutes_comprehensible",
            {"minutes": minutes},
            ended_at,
        )

        await uow.commit()

    return LearnerProgressDTO(
        minutes_comprehensible=progress.minutes_comprehensible,
        current_ci_level=progress.current_ci_level,
    )


async def handle_get_progress(
    query: GetLearnerProgressQuery,
    repo: LearningRepository,
) -> LearnerProgressDTO:
    """Read learner progress."""
    progress = await repo.get_progress(query.user_id)
    if progress is None:
        raise EntityNotFoundError("Progress not found")
    return LearnerProgressDTO(
        minutes_comprehensible=progress.minutes_comprehensible,
        current_ci_level=progress.current_ci_level,
    )
