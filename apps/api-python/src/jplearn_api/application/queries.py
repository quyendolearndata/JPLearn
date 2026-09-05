"""Application queries (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetFlagsQuery:
    pass


@dataclass(frozen=True)
class AuthenticateUserQuery:
    email: str
    password: str
    secret: str


@dataclass(frozen=True)
class GetCurrentUserQuery:
    user_id: str
