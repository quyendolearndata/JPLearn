from __future__ import annotations

from datetime import datetime
from typing import Protocol

from jplearn_api.application.read_models import CatalogItemPublicDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.identity import UserAccount


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


class CatalogRepository(Protocol):
    """Port for loading and persisting CatalogItem aggregates."""

    async def get_by_id(self, item_id: str) -> CatalogItem | None:
        ...

    async def add(self, item: CatalogItem) -> None:
        ...

    async def update(self, item: CatalogItem) -> None:
        ...

    async def topic_exists(self, topic_id: str) -> bool:
        ...


class CatalogQueryPort(Protocol):
    """Port for reading published catalog items."""

    async def list_published(self, ci_level: int | None) -> list[CatalogItemPublicDTO]:
        ...
