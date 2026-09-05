from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import UpdateFlagsCommand
from jplearn_api.application.handlers.flags import handle_get_flags, handle_update_flags
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import create_flags_repository, create_uow
from jplearn_api.deps import get_session
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
    _user: UserDTO = Depends(require_user),
) -> Flags:
    repo = create_flags_repository(session)
    result = await handle_get_flags(repo)
    return Flags.model_validate(result)


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
    _admin: UserDTO = Depends(require_roles("admin")),
) -> Flags:
    uow = create_uow(session)
    repo = create_flags_repository(session)
    cmd = UpdateFlagsCommand(flags=body.model_dump())
    updated = await handle_update_flags(cmd, uow, repo)
    return Flags.model_validate(updated)
