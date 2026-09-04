import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jplearn_api.datetime_adapt import to_naive_utc
from jplearn_api.models import LearnerProgress, User, UserRole
from jplearn_api.password import hash_password, verify_password
from jplearn_api.schemas import AuthSession, UserPublic
from jplearn_api.tokens import sign_access_token


def to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        roles=[role.role for role in user.roles],
    )


def session_payload(user: User, secret: str) -> AuthSession:
    return AuthSession(
        access_token=sign_access_token(
            user_id=user.id,
            email=user.email,
            ver=user.token_version,
            secret=secret,
        ),
        user=to_public(user),
    )


async def load_user(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id),
    )
    return result.scalar_one_or_none()


async def register(session: AsyncSession, secret: str, email: str, password: str) -> AuthSession:
    if not isinstance(password, str) or len(password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters")
    normalized = email.strip().lower() if isinstance(email, str) else ""
    if not normalized:
        raise HTTPException(status_code=400, detail="Email is required")
    now = to_naive_utc(datetime.now(UTC))
    pw_hash = await asyncio.to_thread(hash_password, password)
    user = User(
        id=str(uuid4()),
        email=normalized,
        password_hash=pw_hash,
        token_version=0,
        created_at=now,
    )
    session.add(user)
    try:
        await session.flush()
        session.add(UserRole(user_id=user.id, role="learner"))
        session.add(
            LearnerProgress(
                user_id=user.id,
                minutes_comprehensible=0,
                current_ci_level=0,
                updated_at=now,
            ),
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        detail = str(getattr(error, "orig", error)).lower()
        if "users_email" in detail or ("email" in detail and "unique" in detail):
            raise HTTPException(status_code=409, detail="Email already registered") from None
        raise
    loaded = await load_user(session, user.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Internal server error")
    return session_payload(loaded, secret)


async def login(session: AsyncSession, secret: str, email: object, password: object) -> AuthSession:
    if not isinstance(email, str) or not isinstance(password, str):
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = await session.execute(
        select(User).options(selectinload(User.roles)).where(User.email == email.strip().lower()),
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    valid = await asyncio.to_thread(verify_password, user.password_hash, password)
    if not valid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return session_payload(user, secret)


async def logout(session: AsyncSession, user: User) -> None:
    user.token_version += 1
    await session.commit()
