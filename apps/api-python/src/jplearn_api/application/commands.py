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


@dataclass(frozen=True)
class StartLearningSessionCommand:
    user_id: str
    device_class: str
    idempotency_key: str | None = None
    request_hash: str | None = None


@dataclass(frozen=True)
class EndLearningSessionCommand:
    user_id: str
    session_id: str


@dataclass(frozen=True)
class UpdateDraftCatalogItemCommand:
    item_id: str
    revision: int
    topic_id: str | None = None
    ci_level: int | None = None
    duration_seconds: int | None = None
    media_type: str | None = None
    visual_support: str | None = None
    title_internal: str | None = None

