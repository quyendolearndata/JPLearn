"""Deterministic integrity inspection for an HLS bundle in abstract storage."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from jplearn_api.application.ports.storage import StoragePort
from jplearn_api.domain.errors import InvalidDomainStateError

_URI_ATTRIBUTE = re.compile(r'URI="([^"]+)"')
_ALLOWED_SUFFIXES = {".m3u8", ".ts", ".m4s", ".mp4", ".vtt"}
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class HlsBundleInspection:
    sha256: str
    file_count: int
    total_bytes: int


def _validate_relative_uri(uri: str) -> str:
    candidate = uri.strip()
    path = PurePosixPath(candidate)
    if (
        not candidate
        or "://" in candidate
        or candidate.startswith(("/", "\\"))
        or len(path.parts) != 1
        or ".." in path.parts
        or path.suffix.lower() not in _ALLOWED_SUFFIXES
    ):
        raise InvalidDomainStateError("HLS manifest contains an unsupported or external URI")
    return candidate


async def _read_bytes(storage: StoragePort, key: str, *, limit: int | None = None) -> bytes:
    stream = await storage.open_read(key)
    chunks: list[bytes] = []
    total = 0
    async for chunk in stream:
        total += len(chunk)
        if limit is not None and total > limit:
            raise InvalidDomainStateError("HLS manifest exceeds the supported size")
        chunks.append(chunk)
    return b"".join(chunks)


async def inspect_hls_bundle(storage: StoragePort, asset_id: str) -> HlsBundleInspection:
    """Hash the root manifest and every transitively referenced local HLS file."""
    prefix = f"hls/{asset_id}/"
    available = set(await storage.list_keys(prefix))
    root = f"{prefix}index.m3u8"
    if root not in available:
        raise InvalidDomainStateError("HLS manifest missing on disk; transcode this asset first")

    files = {root}
    manifests = [root]
    while manifests:
        manifest_key = manifests.pop()
        raw = await _read_bytes(storage, manifest_key, limit=_MAX_MANIFEST_BYTES)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidDomainStateError("HLS manifest must be UTF-8") from exc
        references: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                references.extend(_URI_ATTRIBUTE.findall(stripped))
            else:
                references.append(stripped)
        for uri in references:
            name = _validate_relative_uri(uri)
            key = f"{prefix}{name}"
            if key not in available:
                raise InvalidDomainStateError(f"HLS bundle is incomplete: missing '{name}'")
            if key not in files:
                files.add(key)
                if name.lower().endswith(".m3u8"):
                    manifests.append(key)

    if not any(PurePosixPath(key).suffix.lower() in {".ts", ".m4s", ".mp4"} for key in files):
        raise InvalidDomainStateError("HLS bundle must reference at least one media segment")

    digest = hashlib.sha256()
    total_bytes = 0
    for key in sorted(files):
        relative = key.removeprefix(prefix).encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        stream = await storage.open_read(key)
        file_digest = hashlib.sha256()
        file_bytes = 0
        async for chunk in stream:
            total_bytes += len(chunk)
            file_bytes += len(chunk)
            file_digest.update(chunk)
        digest.update(file_bytes.to_bytes(8, "big"))
        digest.update(file_digest.digest())
    return HlsBundleInspection(digest.hexdigest(), len(files), total_bytes)
