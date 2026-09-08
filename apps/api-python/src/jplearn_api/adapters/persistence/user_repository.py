"""SQLAlchemy implementation of UserRepository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.adapters.persistence.models import LearnerProgress, User, UserRole
from jplearn_api.application.ports.repositories import UserRepository
from jplearn_api.domain.errors import DuplicateEmailError
from jplearn_api.domain.identity import UserAccount


def _to_domain(user_orm: User) -> UserAccount:
    return UserAccount(
        id=user_orm.id,
        email=user_orm.email,
        password_hash=user_orm.password_hash,
        token_version=user_orm.token_version,
        created_at=user_orm.created_at,
        roles=[r.role for r in user_orm.roles],
    )


class SqlAlchemyUserRepository(UserRepository):
    """PostgreSQL/SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> UserAccount | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.roles)).where(User.id == user_id),
        )
        user_orm = result.scalar_one_or_none()
        return _to_domain(user_orm) if user_orm else None

    async def get_by_email(self, email: str) -> UserAccount | None:
        normalized = UserAccount.normalize_email(email)
        result = await self._session.execute(
            select(User).options(selectinload(User.roles)).where(User.email == normalized),
        )
        user_orm = result.scalar_one_or_none()
        return _to_domain(user_orm) if user_orm else None

    async def add(self, user: UserAccount) -> None:
        user_orm = User(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            token_version=user.token_version,
            created_at=user.created_at,
        )
        self._session.add(user_orm)
        try:
            await self._session.flush()
        except IntegrityError as error:
            detail = str(getattr(error, "orig", error)).lower()
            if "users_email" in detail or ("email" in detail and "unique" in detail):
                raise DuplicateEmailError("Email already registered") from None
            raise

    async def update(self, user: UserAccount) -> None:
        result = await self._session.execute(
            select(User).where(User.id == user.id),
        )
        user_orm = result.scalar_one_or_none()
        if user_orm is not None:
            user_orm.token_version = user.token_version
            await self._session.flush()

    async def add_role(self, user_id: str, role: str) -> None:
        self._session.add(UserRole(user_id=user_id, role=role))
        await self._session.flush()

    async def add_initial_progress(self, user_id: str, now: datetime) -> None:
        self._session.add(
            LearnerProgress(
                user_id=user_id,
                minutes_comprehensible=0,
                current_ci_level=0,
                updated_at=now,
            ),
        )
        await self._session.flush()
