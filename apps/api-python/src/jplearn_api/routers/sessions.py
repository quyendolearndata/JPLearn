from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api import sessions_service
from jplearn_api.deps import UUIDPath, get_session
from jplearn_api.models import User
from jplearn_api.schemas import LearnerProgressPublic, LearningSessionPublic, SessionStartBody
from jplearn_api.security import require_user
from jplearn_api.session_policy import (
    ForbiddenSession,
    LearnerProgressNotFound,
    SessionAlreadyEnded,
    SessionNotFound,
)

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
    user: User = Depends(require_user),
) -> LearningSessionPublic:
    if body.device_class not in DEVICE_CLASSES:
        raise HTTPException(status_code=400, detail="device_class is required")
    try:
        return await sessions_service.start(session, user.id, body.device_class)
    except LearnerProgressNotFound:
        raise HTTPException(status_code=500, detail="Missing learner progress")


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
    user: User = Depends(require_user),
) -> LearnerProgressPublic:
    try:
        return await sessions_service.end(session, user.id, id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail="Session not found")
    except ForbiddenSession:
        raise HTTPException(status_code=403, detail="Forbidden")
    except SessionAlreadyEnded:
        raise HTTPException(status_code=400, detail="Session already ended")
    except LearnerProgressNotFound:
        raise HTTPException(status_code=500, detail="Missing learner progress")


@router.get(
    "/progress",
    response_model=LearnerProgressPublic,
    operation_id="getProgress",
    tags=["Progress"],
    openapi_extra={"x-jplearn-fr": ["FR-PRG-001", "FR-PRG-002", "FR-PRG-003", "FR-PRG-004"]},
)
async def get_progress(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> LearnerProgressPublic:
    try:
        return await sessions_service.progress(session, user.id)
    except LearnerProgressNotFound:
        raise HTTPException(status_code=404, detail="Progress not found")

