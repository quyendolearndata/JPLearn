from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from jplearn_api.application.commands import LogoutUserCommand, RegisterUserCommand
from jplearn_api.application.handlers.identity import handle_login, handle_logout, handle_register
from jplearn_api.application.queries import AuthenticateUserQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.bootstrap import (
    create_password_hasher,
    create_token_service,
    create_uow,
    create_user_repository,
)
from jplearn_api.deps import get_session
from jplearn_api.domain.errors import DomainError
from jplearn_api.entrypoints.http.error_mapping import map_domain_error_to_http
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
    uow = create_uow(session)
    user_repo = create_user_repository(session)
    hasher = create_password_hasher()
    token_service = create_token_service()
    cmd = RegisterUserCommand(
        email=body.email,
        password=body.password,
        secret=request.app.state.settings.jwt_secret,
    )
    try:
        dto = await handle_register(cmd, uow, user_repo, hasher, token_service)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return AuthSession(
        access_token=dto.access_token,
        user=UserPublic(
            id=dto.user.id,
            email=dto.user.email,
            roles=dto.user.roles,
        ),
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
    user_repo = create_user_repository(session)
    hasher = create_password_hasher()
    token_service = create_token_service()
    query = AuthenticateUserQuery(
        email=body.email,
        password=body.password,
        secret=request.app.state.settings.jwt_secret,
    )
    try:
        dto = await handle_login(query, user_repo, hasher, token_service)
    except DomainError as exc:
        raise map_domain_error_to_http(exc) from exc

    return AuthSession(
        access_token=dto.access_token,
        user=UserPublic(
            id=dto.user.id,
            email=dto.user.email,
            roles=dto.user.roles,
        ),
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
    user: UserDTO = Depends(require_user),
) -> Response:
    uow = create_uow(session)
    user_repo = create_user_repository(session)
    cmd = LogoutUserCommand(user_id=user.id)
    await handle_logout(cmd, uow, user_repo)
    return Response(status_code=204)


@router.get(
    "/me",
    response_model=UserPublic,
    operation_id="getMe",
    openapi_extra={"x-jplearn-fr": ["FR-ID-002", "FR-ID-004"]},
)
async def me(user: UserDTO = Depends(require_user)) -> UserPublic:
    user_roles = [getattr(r, "role", r) for r in user.roles]
    return UserPublic(
        id=user.id,
        email=user.email,
        roles=user_roles,
    )
