from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.deps import get_session
from jplearn_api.models import User
from jplearn_api.tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


async def require_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = decode_access_token(creds.credentials, request.app.state.settings.jwt_secret)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized") from None
    result = await session.execute(
        select(User).options(selectinload(User.roles)).where(User.id == payload["sub"]),
    )
    user = result.scalar_one_or_none()
    if user is None or payload["ver"] != user.token_version:
        raise HTTPException(status_code=401, detail="Unauthorized")
    request.state.user = user
    return user
