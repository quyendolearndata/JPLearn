"""Application commands (Pure Python dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateFlagsCommand:
    flags: dict[str, bool]


@dataclass(frozen=True)
class RegisterUserCommand:
    email: str
    password: str
    secret: str


@dataclass(frozen=True)
class LogoutUserCommand:
    user_id: str
