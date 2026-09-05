"""Storage port protocol (Pure Python)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class StoragePort(Protocol):
    """Abstract storage port for blob storage operations."""

    async def stage(self, temp_key: str, stream: AsyncIterator[bytes]) -> int:
        ...

    async def promote(self, temp_key: str, final_key: str) -> None:
        ...

    async def delete(self, key: str) -> None:
        ...

    async def exists(self, key: str) -> bool:
        ...

    async def read_range(
        self,
        key: str,
        offset: int,
        length: int,
    ) -> AsyncIterator[bytes]:
        ...

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        ...

    async def get_metadata(self, key: str) -> dict[str, Any]:
        ...

    async def check_readiness(self) -> bool:
        ...

    async def close(self) -> None:
        ...
