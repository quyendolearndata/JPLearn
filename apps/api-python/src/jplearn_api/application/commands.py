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


@dataclass(frozen=True)
class CreateCatalogItemCommand:
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    visual_support: str
    title_internal: str
    created_by: str


@dataclass(frozen=True)
class SubmitCatalogForQaCommand:
    item_id: str


@dataclass(frozen=True)
class PublishCatalogItemCommand:
    item_id: str


@dataclass(frozen=True)
class UnpublishCatalogItemCommand:
    item_id: str


@dataclass(frozen=True)
class ArchiveCatalogItemCommand:
    item_id: str
