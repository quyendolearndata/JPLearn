from time import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.adapters.persistence.models import User
from jplearn_api.application.read_models import UserDTO
from jplearn_api.deps import get_session
from jplearn_api.signed_url import verify_media_sig
from jplearn_api.tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


async def require_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserDTO:
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
    user_dto = UserDTO(
        id=user.id,
        email=user.email,
        roles=[role.role for role in user.roles],
    )
    request.state.user = user_dto
    return user_dto


async def require_media_access(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    settings = request.app.state.settings
    header = request.headers.get("authorization")
    if header and header.startswith("Bearer "):
        try:
            payload = decode_access_token(header[7:], settings.jwt_secret)
            result = await session.execute(
                select(User).options(selectinload(User.roles)).where(User.id == payload["sub"]),
            )
            user = result.scalar_one_or_none()
            if user is None or payload["ver"] != user.token_version:
                raise HTTPException(status_code=401, detail="Unauthorized")
            user_dto = UserDTO(
                id=user.id,
                email=user.email,
                roles=[role.role for role in user.roles],
            )
            request.state.user = user_dto
            return
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Unauthorized") from None

    asset_id = request.path_params.get("id")
    exp_raw = request.query_params.get("exp")
    sig = request.query_params.get("sig") or ""
    if asset_id and exp_raw is not None:
        try:
            exp = int(exp_raw)
        except ValueError:
            exp = -1
        secret = getattr(settings, "media_signing_secret", None) or settings.jwt_secret
        if verify_media_sig(asset_id=asset_id, exp=exp, sig=sig, secret=secret, now_sec=int(time())):
            return

    raise HTTPException(status_code=401, detail="Unauthorized")
