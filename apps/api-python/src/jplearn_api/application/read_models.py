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


@dataclass(frozen=True)
class CatalogItemStaffDTO:
    id: str
    topic_id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    visual_support: str
    title_internal: str
    has_l1_translation: bool
    status: str


@dataclass(frozen=True)
class CatalogItemPublicDTO:
    id: str
    ci_level: int
    duration_seconds: int
    media_type: str
    topic_id: str
    visual_support: str
    playback_url: str | None
    hls_url: str | None
