"""Storage port protocol (Pure Python)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol
from jplearn_api.application.ports.media_probe import MediaInspection


class StoragePort(Protocol):
    """Abstract storage port for blob storage operations."""

    async def inspect_media(self, key: str) -> "MediaInspection": ...

    async def stage_stream(
        self,
        temp_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int = 500 * 1024 * 1024,
    ) -> int:
        ...

    async def promote(self, temp_key: str, final_key: str) -> None:
        ...

    async def exists(self, key: str) -> bool:
        ...

    async def delete(self, key: str) -> bool:
        ...

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        ...

    async def open_read_range(
        self,
        key: str,
        start: int,
        length: int,
    ) -> AsyncIterator[bytes]:
        ...

    async def get_metadata(self, key: str) -> Any:
        ...

    async def list_keys(self, prefix: str = "") -> list[str]:
        ...

    async def check_ready(self) -> tuple[bool, str]:
        ...

    async def close(self) -> None:
        ...
