from collections.abc import Callable

from fastapi import Depends, HTTPException

from jplearn_api.models import User
from jplearn_api.security import require_user


def require_roles(*roles: str) -> Callable[..., User]:
    async def _check(user: User = Depends(require_user)) -> User:
        have = {role.role for role in user.roles}
        if not have.intersection(roles):
            raise HTTPException(status_code=403, detail="Forbidden resource")
        return user

    return _check
