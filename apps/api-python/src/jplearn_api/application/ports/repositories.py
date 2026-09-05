"""Repository ports (Pure Python, protocol-based)."""

from __future__ import annotations

from typing import Protocol


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
