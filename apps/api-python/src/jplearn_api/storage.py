from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

CHUNK_SIZE = 64 * 1024  # 64 KB
MAX_MEDIA_BYTES = 500 * 1024 * 1024  # 500 MB max for video per ADR-005


@dataclass(frozen=True)
class StorageMetadata:
    size: int
    content_type: str | None = None
    mtime: float | None = None


class StoragePort(ABC):
    @abstractmethod
    async def stage_stream(
        self,
        temp_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int = MAX_MEDIA_BYTES,
    ) -> int:
        """Stream chunks into temporary staging key. Returns total bytes.
        Raises ValueError if empty or exceeds max_bytes.
        """
        ...

    @abstractmethod
    async def promote(self, temp_key: str, final_key: str) -> None:
        """Promote a staged file into final key."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in storage."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from storage. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        """Stream chunks of file content asynchronously without loading whole file into RAM.
        Raises FileNotFoundError if missing.
        """
        ...

    @abstractmethod
    async def get_metadata(self, key: str) -> StorageMetadata:
        """Get object metadata. Raises FileNotFoundError if missing."""
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List keys in storage matching prefix."""
        ...

    @abstractmethod
    async def check_ready(self) -> tuple[bool, str]:
        """Verify storage write, read, and delete capability. Returns (ok, message)."""
        ...


class LocalFilesystemStorage(StoragePort):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Normalize and guard against directory traversal (including sibling prefix, absolute path, and escape)
        if Path(key).is_absolute() or key.startswith(("/", "\\")):
            raise ValueError(f"Directory traversal detected for key: {key}")
        resolved = (self.root / key).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"Directory traversal detected for key: {key}")
        return resolved

    async def stage_stream(
        self,
        temp_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int = MAX_MEDIA_BYTES,
    ) -> int:
        temp_path = self._resolve(temp_key)
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0

        try:
            with temp_path.open("wb") as f:
                async for chunk in stream:
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise ValueError(f"File size exceeds limit of {max_bytes} bytes")
                    f.write(chunk)

            if total_bytes == 0:
                temp_path.unlink(missing_ok=True)
                raise ValueError("File must not be empty")

            return total_bytes
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    async def promote(self, temp_key: str, final_key: str) -> None:
        temp_path = self._resolve(temp_key)
        if not temp_path.exists():
            raise FileNotFoundError(f"Staging file not found: {temp_key}")
        final_path = self._resolve(final_key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.replace(final_path)

    async def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except ValueError:
            return False

    async def delete(self, key: str) -> bool:
        try:
            path = self._resolve(key)
            if path.is_file():
                path.unlink()
                return True
            return False
        except ValueError:
            return False

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {key}")

        loop = asyncio.get_running_loop()
        file_handle = await loop.run_in_executor(None, path.open, "rb")

        async def _generator():
            try:
                while True:
                    chunk = await loop.run_in_executor(None, file_handle.read, CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await loop.run_in_executor(None, file_handle.close)

        return _generator()

    async def get_metadata(self, key: str) -> StorageMetadata:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {key}")
        stat = path.stat()
        return StorageMetadata(size=stat.st_size, mtime=stat.st_mtime)

    async def list_keys(self, prefix: str = "") -> list[str]:
        keys = []
        for p in self.root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(prefix) and not rel.endswith(".part"):
                    keys.append(rel)
        return keys

    async def check_ready(self) -> tuple[bool, str]:
        probe_key = "__probe__/probe.tmp"
        try:
            probe_path = self._resolve(probe_key)
            probe_path.parent.mkdir(parents=True, exist_ok=True)
            probe_content = b"readiness_probe_active"

            def _sync_probe():
                with probe_path.open("wb") as f:
                    f.write(probe_content)
                    f.flush()
                    os.fsync(f.fileno())
                with probe_path.open("rb") as f:
                    read_back = f.read()
                if read_back != probe_content:
                    raise RuntimeError("Readback mismatch during storage probe")
                probe_path.unlink(missing_ok=True)

            await asyncio.to_thread(_sync_probe)
            return True, "up"
        except Exception as exc:
            return False, f"storage probe failed: {exc}"


class InMemoryStorage(StoragePort):
    """Fake Object Storage adapter for contract testing without filesystem dependency."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.is_healthy: bool = True

    async def stage_stream(
        self,
        temp_key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int = MAX_MEDIA_BYTES,
    ) -> int:
        chunks = []
        total = 0
        async for chunk in stream:
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"File size exceeds limit of {max_bytes} bytes")
            chunks.append(chunk)

        if total == 0:
            raise ValueError("File must not be empty")

        self.objects[temp_key] = b"".join(chunks)
        return total

    async def promote(self, temp_key: str, final_key: str) -> None:
        if temp_key not in self.objects:
            raise FileNotFoundError(f"Staging file not found: {temp_key}")
        self.objects[final_key] = self.objects.pop(temp_key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def delete(self, key: str) -> bool:
        return self.objects.pop(key, None) is not None

    async def open_read(self, key: str) -> AsyncIterator[bytes]:
        if key not in self.objects:
            raise FileNotFoundError(f"File not found: {key}")
        data = self.objects[key]

        async def _generator():
            offset = 0
            while offset < len(data):
                yield data[offset : offset + CHUNK_SIZE]
                offset += CHUNK_SIZE

        return _generator()

    async def get_metadata(self, key: str) -> StorageMetadata:
        if key not in self.objects:
            raise FileNotFoundError(f"File not found: {key}")
        return StorageMetadata(size=len(self.objects[key]))

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self.objects if k.startswith(prefix) and not k.endswith(".part")]

    async def check_ready(self) -> tuple[bool, str]:
        if not self.is_healthy:
            return False, "in-memory storage simulated failure"
        return True, "up"
