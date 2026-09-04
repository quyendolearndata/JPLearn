from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.deps import get_session
from jplearn_api.flags_service import get_flags, update_flags
from jplearn_api.models import User
from jplearn_api.roles import require_roles
from jplearn_api.schemas import Flags
from jplearn_api.security import require_user

router = APIRouter(tags=["Flags"])


@router.get(
    "/flags",
    response_model=Flags,
    operation_id="getFlags",
    openapi_extra={"x-jplearn-fr": ["FR-FLG-001", "FR-FLG-002"]},
)
async def read_flags(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_user),
) -> Flags:
    return await get_flags(session)


@router.patch(
    "/staff/flags",
    response_model=Flags,
    operation_id="patchFlags",
    openapi_extra={"x-jplearn-fr": ["FR-FLG-001"]},
    responses={403: {"description": "Admin only"}},
)
async def patch_flags(
    body: Flags,
    session: AsyncSession = Depends(get_session),
    _admin: User = Depends(require_roles("admin")),
) -> Flags:
    return await update_flags(session, body)
