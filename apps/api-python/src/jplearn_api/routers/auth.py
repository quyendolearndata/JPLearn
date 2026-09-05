from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api import auth_service
from jplearn_api.deps import get_session
from jplearn_api.models import User
from jplearn_api.schemas import AuthSession, LoginBody, RegisterBody, UserPublic
from jplearn_api.security import require_user

router = APIRouter(tags=["Identity"])


@router.post(
    "/auth/register",
    status_code=201,
    response_model=AuthSession,
    operation_id="register",
    openapi_extra={"x-jplearn-fr": ["FR-ID-001"]},
)
async def register(
    body: RegisterBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthSession:
    return await auth_service.register(
        session,
        request.app.state.settings.jwt_secret,
        body.email,
        body.password,
    )


@router.post(
    "/auth/login",
    status_code=200,
    response_model=AuthSession,
    operation_id="login",
    openapi_extra={"x-jplearn-fr": ["FR-ID-001", "FR-ID-002"]},
    responses={401: {"description": "Invalid credentials"}},
)
async def login(
    body: LoginBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthSession:
    return await auth_service.login(
        session,
        request.app.state.settings.jwt_secret,
        body.email,
        body.password,
    )


@router.post(
    "/auth/logout",
    status_code=204,
    operation_id="logout",
    openapi_extra={"x-jplearn-fr": ["FR-ID-003"]},
    responses={
        204: {"description": "Invalidates every access_token for this user (all devices); tokenVersion increment (FR-ID-003)"},
        401: {"description": "Missing or invalid Bearer"},
    },
)
async def logout(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> Response:
    await auth_service.logout(session, user)
    return Response(status_code=204)


@router.get(
    "/me",
    response_model=UserPublic,
    operation_id="getMe",
    openapi_extra={"x-jplearn-fr": ["FR-ID-002", "FR-ID-004"]},
)
async def me(user: User = Depends(require_user)) -> UserPublic:
    return auth_service.to_public(user)
