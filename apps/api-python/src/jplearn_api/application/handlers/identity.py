"""Identity use case handlers (Pure Python)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from jplearn_api.application.commands import LogoutUserCommand, RegisterUserCommand
from jplearn_api.application.ports.repositories import UserRepository
from jplearn_api.application.ports.security import PasswordHasher, TokenService
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import AuthenticateUserQuery, GetCurrentUserQuery
from jplearn_api.application.read_models import AuthSessionDTO, UserDTO
from jplearn_api.domain.errors import EntityNotFoundError, InvalidDomainStateError, UnauthorizedError
from jplearn_api.domain.identity import UserAccount


def _to_user_dto(user: UserAccount) -> UserDTO:
    return UserDTO(id=user.id, email=user.email, roles=list(user.roles))


async def handle_register(
    cmd: RegisterUserCommand,
    uow: AsyncUnitOfWork,
    hasher: PasswordHasher,
    token_service: TokenService,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC).replace(tzinfo=None),
    id_generator: Callable[[], str] = lambda: str(uuid4()),
) -> AuthSessionDTO:
    """Atomic registration of user, learner role, and initial progress."""
    if not isinstance(cmd.password, str) or len(cmd.password) < 10:
        raise InvalidDomainStateError("Password must be at least 10 characters")
    email = UserAccount.normalize_email(cmd.email)
    if not email:
        raise InvalidDomainStateError("Email is required")

    pw_hash = await hasher.hash_password(cmd.password)
    now = clock()
    user_id = id_generator()

    user = UserAccount(
        id=user_id,
        email=email,
        password_hash=pw_hash,
        token_version=0,
        created_at=now,
        roles=[],
    )

    async with uow:
        await uow.users.add(user)
        await uow.users.add_role(user.id, "learner")
        await uow.users.add_initial_progress(user.id, now)
        await uow.commit()

    user.roles = ["learner"]

    token = token_service.sign_access_token(
        user_id=user.id,
        email=user.email,
        token_version=user.token_version,
        secret=cmd.secret,
    )
    return AuthSessionDTO(access_token=token, user=_to_user_dto(user))


async def handle_login(
    query: AuthenticateUserQuery,
    user_repo: UserRepository,
    hasher: PasswordHasher,
    token_service: TokenService,
) -> AuthSessionDTO:
    """Authenticate user with email and password."""
    if not isinstance(query.email, str) or not isinstance(query.password, str):
        raise UnauthorizedError("Unauthorized")
    email = UserAccount.normalize_email(query.email)
    if not email:
        raise UnauthorizedError("Unauthorized")

    user = await user_repo.get_by_email(email)
    if user is None:
        raise UnauthorizedError("Unauthorized")

    is_valid = await hasher.verify_password(user.password_hash, query.password)
    if not is_valid:
        raise UnauthorizedError("Unauthorized")

    token = token_service.sign_access_token(
        user_id=user.id,
        email=user.email,
        token_version=user.token_version,
        secret=query.secret,
    )
    return AuthSessionDTO(access_token=token, user=_to_user_dto(user))


async def handle_logout(
    cmd: LogoutUserCommand,
    uow: AsyncUnitOfWork,
) -> None:
    """Logout by incrementing token version in an atomic transaction."""
    async with uow:
        user = await uow.users.get_by_id(cmd.user_id)
        if user is not None:
            user.increment_token_version()
            await uow.users.update(user)
            await uow.commit()


async def handle_get_current_user(
    query: GetCurrentUserQuery,
    user_repo: UserRepository,
) -> UserDTO:
    """Retrieve current user profile."""
    user = await user_repo.get_by_id(query.user_id)
    if user is None:
        raise EntityNotFoundError("User not found")
    return _to_user_dto(user)
