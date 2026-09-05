from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import EndLearningSessionCommand, StartLearningSessionCommand
from jplearn_api.application.handlers.learning import (
    handle_end_session,
    handle_get_progress,
    handle_start_session,
)
from jplearn_api.application.queries import GetLearnerProgressQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_learning_repository, create_uow
from jplearn_api.datetime_adapt import to_json_z
from jplearn_api.deps import UUIDPath, get_session
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    ForbiddenError,
    SessionAlreadyEndedError,
)
from jplearn_api.schemas import LearnerProgressPublic, LearningSessionPublic, SessionStartBody
from jplearn_api.security import require_user

router = APIRouter(tags=["Session", "Progress"])

DEVICE_CLASSES = ("web", "phone", "ipad")


@router.post(
    "/sessions",
    status_code=201,
    response_model=LearningSessionPublic,
    operation_id="startSession",
    tags=["Session"],
    openapi_extra={"x-jplearn-fr": ["FR-SES-001", "FR-SES-003", "FR-EVT-001", "FR-EVT-003"]},
)
async def start_session(
    body: SessionStartBody,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> LearningSessionPublic:
    if body.device_class not in DEVICE_CLASSES:
        raise HTTPException(status_code=400, detail="device_class is required")
    uow = create_uow(session)
    cmd = StartLearningSessionCommand(user_id=user.id, device_class=body.device_class)
    try:
        dto = await handle_start_session(cmd, uow)
    except EntityNotFoundError:
        raise HTTPException(status_code=500, detail="Missing learner progress")

    return LearningSessionPublic(
        id=dto.id,
        device_class=dto.device_class,
        started_at=to_json_z(dto.started_at),
        ended_at=to_json_z(dto.ended_at) if dto.ended_at else None,
        duration_seconds=dto.duration_seconds,
    )


@router.post(
    "/sessions/{id}/end",
    response_model=LearnerProgressPublic,
    operation_id="endSession",
    tags=["Session"],
    openapi_extra={"x-jplearn-fr": ["FR-SES-002", "FR-PRG-001", "FR-EVT-001", "FR-EVT-002"]},
    responses={
        400: {"description": "Session already ended"},
    },
)
async def end_session(
    id: UUIDPath,
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> LearnerProgressPublic:
    uow = create_uow(session)
    cmd = EndLearningSessionCommand(user_id=user.id, session_id=id)
    try:
        dto = await handle_end_session(cmd, uow)
    except SessionAlreadyEndedError:
        raise HTTPException(status_code=400, detail="Session already ended")
    except ForbiddenError:
        raise HTTPException(status_code=403, detail="Forbidden")
    except EntityNotFoundError as exc:
        if exc.message == "Missing learner progress":
            raise HTTPException(status_code=500, detail="Missing learner progress")
        raise HTTPException(status_code=404, detail="Session not found")

    return LearnerProgressPublic(
        minutes_comprehensible=dto.minutes_comprehensible,
        current_ci_level=dto.current_ci_level,
    )


@router.get(
    "/progress",
    response_model=LearnerProgressPublic,
    operation_id="getProgress",
    tags=["Progress"],
    openapi_extra={"x-jplearn-fr": ["FR-PRG-001", "FR-PRG-002", "FR-PRG-003", "FR-PRG-004"]},
)
async def get_progress(
    session: AsyncSession = Depends(get_session),
    user: UserDTO = Depends(require_user),
) -> LearnerProgressPublic:
    repo = create_learning_repository(session)
    query = GetLearnerProgressQuery(user_id=user.id)
    try:
        dto = await handle_get_progress(query, repo)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail="Progress not found")

    return LearnerProgressPublic(
        minutes_comprehensible=dto.minutes_comprehensible,
        current_ci_level=dto.current_ci_level,
    )
