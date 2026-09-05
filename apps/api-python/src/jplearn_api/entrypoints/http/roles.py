from collections.abc import Callable

from fastapi import Depends, HTTPException

from jplearn_api.application.read_models import UserDTO
from jplearn_api.entrypoints.http.security import require_user


def require_roles(*roles: str) -> Callable[..., UserDTO]:
    async def _check(user: UserDTO = Depends(require_user)) -> UserDTO:
        have = {role.role if hasattr(role, "role") else str(role) for role in user.roles}
        if not have.intersection(roles):
            raise HTTPException(status_code=403, detail="Forbidden resource")
        return user

    return _check
