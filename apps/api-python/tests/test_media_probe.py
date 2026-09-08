import asyncio
import shutil

import pytest

from jplearn_api.adapters.storage.local import LocalFilesystemStorage


@pytest.mark.real_media_probe
@pytest.mark.asyncio
async def test_real_ffprobe_measures_and_detects_source_changes(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe unavailable")
    path = tmp_path / "source.mp4"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=32x32:d=1",
        "-c:v",
        "mpeg4",
        str(path),
    )
    assert await proc.wait() == 0
    storage = LocalFilesystemStorage(str(tmp_path))
    try:
        first = await storage.inspect_media("source.mp4")
        assert 900 <= first.duration_ms <= 1100
        path.write_bytes(path.read_bytes() + b"changed")
        second = await storage.inspect_media("source.mp4")
        assert second.sha256 != first.sha256
        (tmp_path / "invalid.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        with pytest.raises(ValueError):
            await storage.inspect_media("invalid.mp4")
    finally:
        await storage.close()
