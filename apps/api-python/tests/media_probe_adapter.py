"""Explicit fixture inspector: synthetic MP4 test bytes are not valid ffprobe inputs."""
import hashlib
from jplearn_api.application.ports.media_probe import MediaInspection

async def fixture_inspection(storage, key):
    stream = await storage.open_read(key)
    digest = hashlib.sha256()
    async for chunk in stream:
        digest.update(chunk)
    return MediaInspection(duration_ms=3_600_000, sha256=digest.hexdigest())
