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


@dataclass(frozen=True)
class ListPublishedCatalogQuery:
    ci_level: int | None = None


@dataclass(frozen=True)
class GetLearnerProgressQuery:
    user_id: str


@dataclass(frozen=True)
class GetSessionQuery:
    session_id: str
    user_id: str


@dataclass(frozen=True)
class ListStaffCatalogQuery:
    status: str | None = None
    ci_level: int | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class GetStaffCatalogItemQuery:
    item_id: str

