"""Application read models and DTOs (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserDTO:
    id: str
    email: str
    roles: list[str]


@dataclass(frozen=True)
class AuthSessionDTO:
    access_token: str
    user: UserDTO
