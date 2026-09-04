from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
import shutil

CHUNK_SIZE = 64 * 1024  # 64 KB
MAX_MEDIA_BYTES = 500 * 1024 * 1024  # 500 MB max for video


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
    async def get_path(self, key: str) -> Path:
        """Return Path for local file streaming. Raises FileNotFoundError if missing."""
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List keys in storage matching prefix."""
        ...


class LocalFilesystemStorage(StoragePort):
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        resolved = (self.root / key).resolve()
        if not str(resolved).startswith(str(self.root)):
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

    async def get_path(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {key}")
        return path

    async def list_keys(self, prefix: str = "") -> list[str]:
        keys = []
        for p in self.root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root).as_posix()
                if rel.startswith(prefix) and not rel.endswith(".part"):
                    keys.append(rel)
        return keys
