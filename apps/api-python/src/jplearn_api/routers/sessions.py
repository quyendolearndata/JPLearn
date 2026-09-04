from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api import sessions_service
from jplearn_api.deps import get_session
from jplearn_api.models import User
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
    user: User = Depends(require_user),
) -> LearningSessionPublic:
    if body.device_class not in DEVICE_CLASSES:
        raise HTTPException(status_code=400, detail="device_class is required")
    return await sessions_service.start(session, user.id, body.device_class)


@router.post(
    "/sessions/{id}/end",
    response_model=LearnerProgressPublic,
    operation_id="endSession",
    tags=["Session"],
    openapi_extra={"x-jplearn-fr": ["FR-SES-002", "FR-PRG-001", "FR-EVT-001", "FR-EVT-002"]},
)
async def end_session(
    id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> LearnerProgressPublic:
    return await sessions_service.end(session, user.id, id)


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
    return await sessions_service.progress(session, user.id)
