import pytest

from fakes import FakeStoragePort
from jplearn_api.application.media_integrity import inspect_hls_bundle
from jplearn_api.domain.errors import InvalidDomainStateError


@pytest.mark.asyncio
async def test_checksum_is_independent_of_storage_chunk_boundaries():
    class ChunkedStorage(FakeStoragePort):
        async def open_read(self, key):
            async def chunks():
                for byte in self.files[key]:
                    yield bytes([byte])

            return chunks()

    files = {"hls/a/index.m3u8": b"#EXTM3U\nsegment.ts\n", "hls/a/segment.ts": b"payload"}
    normal = FakeStoragePort(set(files))
    chunked = ChunkedStorage(set(files))
    normal.files = dict(files)
    chunked.files = dict(files)
    assert await inspect_hls_bundle(normal, "a") == await inspect_hls_bundle(chunked, "a")
    chunked.files["hls/a/segment.ts"] = b"changed"
    assert (await inspect_hls_bundle(normal, "a")).sha256 != (await inspect_hls_bundle(chunked, "a")).sha256


@pytest.mark.asyncio
async def test_manifest_cycle_without_media_segment_is_rejected():
    files = {"hls/a/index.m3u8": b"#EXTM3U\nchild.m3u8\n", "hls/a/child.m3u8": b"#EXTM3U\nindex.m3u8\n"}
    storage = FakeStoragePort(set(files))
    storage.files = files
    with pytest.raises(InvalidDomainStateError, match="media segment"):
        await inspect_hls_bundle(storage, "a")
