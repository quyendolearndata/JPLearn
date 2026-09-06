from __future__ import annotations

from datetime import datetime
from typing import Protocol

from jplearn_api.application.read_models import CatalogItemPublicDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.identity import UserAccount
from jplearn_api.domain.learning import LearnerProgress, LearningSession
from jplearn_api.domain.media import MediaAsset


class FlagsRepository(Protocol):
    """Port for reading and updating feature flags."""

    async def get_flags(self) -> dict[str, bool]:
        """Fetch current feature flags mapping."""
        ...

    async def update_flags(self, flags: dict[str, bool]) -> dict[str, bool]:
        """Upsert feature flags mapping and return updated values."""
        ...

    async def ensure_defaults(self) -> None:
        """Ensure all default feature flags exist."""
        ...


class UserRepository(Protocol):
    """Port for user persistence and role management."""

    async def get_by_id(self, user_id: str) -> UserAccount | None:
        ...

    async def get_by_email(self, email: str) -> UserAccount | None:
        ...

    async def add(self, user: UserAccount) -> None:
        ...

    async def update(self, user: UserAccount) -> None:
        ...

    async def add_role(self, user_id: str, role: str) -> None:
        ...

    async def add_initial_progress(self, user_id: str, now: datetime) -> None:
        ...


from enum import Enum
from dataclasses import dataclass


class UpdateDraftResultStatus(str, Enum):
    UPDATED = "updated"
    NOT_FOUND = "not_found"
    WRONG_STATUS = "wrong_status"
    REVISION_CONFLICT = "revision_conflict"


@dataclass(frozen=True)
class UpdateDraftResult:
    status: UpdateDraftResultStatus
    item: CatalogItem | None = None


class CatalogRepository(Protocol):
    """Port for loading and persisting CatalogItem aggregates."""

    async def get_by_id(self, item_id: str) -> CatalogItem | None:
        ...

    async def get_by_id_for_update(self, item_id: str) -> CatalogItem | None:
        """Lock row with SELECT FOR UPDATE to serialize state transitions."""
        ...

    async def add(self, item: CatalogItem) -> None:
        ...

    async def update(self, item: CatalogItem) -> None:
        ...

    async def update_draft_cas(
        self,
        item_id: str,
        expected_revision: int,
        topic_id: str | None = None,
        ci_level: int | None = None,
        duration_seconds: int | None = None,
        media_type: str | None = None,
        visual_support: str | None = None,
        title_internal: str | None = None,
    ) -> UpdateDraftResult:
        """Atomically update a draft item with compare-and-swap on revision."""
        ...

    async def topic_exists(self, topic_id: str) -> bool:
        ...

    async def list_staff(
        self,
        status: str | None = None,
        ci_level: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CatalogItem]:
        ...


class CatalogQueryPort(Protocol):
    """Port for reading published catalog items."""

    async def list_published(self, ci_level: int | None) -> list[CatalogItemPublicDTO]:
        ...


class LearningRepository(Protocol):
    """Port for session and progress persistence with row-locking support."""

    async def acquire_idempotency_lock(self, user_id: str, key: str) -> None:
        """Acquire transaction-scoped advisory lock on (user_id, idempotency_key)."""
        ...

    async def create_session(self, session: LearningSession) -> None:
        ...

    async def get_session(self, session_id: str) -> LearningSession | None:
        ...

    async def lock_and_get_session(self, session_id: str) -> LearningSession | None:
        ...

    async def update_session(self, session: LearningSession) -> None:
        ...

    async def get_idempotency_session(self, user_id: str, key: str) -> tuple[str, str] | None:
        ...

    async def save_idempotency(self, user_id: str, key: str, session_id: str, request_hash: str) -> None:
        ...

    async def upsert_device(self, user_id: str, device_class: str, last_seen_at: datetime) -> None:
        ...

    async def get_progress(self, user_id: str) -> LearnerProgress | None:
        ...

    async def lock_and_get_progress(self, user_id: str) -> LearnerProgress | None:
        ...

    async def update_progress(self, progress: LearnerProgress) -> None:
        ...

    async def record_event(
        self,
        user_id: str,
        session_id: str | None,
        event_type: str,
        payload: dict,
        created_at: datetime,
    ) -> None:
        ...



class MediaRepository(Protocol):
    """Port for loading and persisting media asset metadata."""

    async def get_by_id(self, asset_id: str) -> MediaAsset | None:
        ...

    async def add(self, asset: MediaAsset) -> None:
        ...

    async def update(self, asset: MediaAsset) -> None:
        ...

    async def catalog_item_exists(self, catalog_item_id: str) -> bool:
        ...

    async def list_all_storage_keys(self) -> set[str]:
        ...

    async def storage_key_exists(self, storage_key: str) -> bool:
        ...
