import asyncio
from urllib.parse import urlparse

import asyncpg
import pytest
from helpers import ensure_topics, grant_role, insert_media, register

from jplearn_api.reconciliation import reconcile_orphans
from jplearn_api.storage import LocalFilesystemStorage

TINY_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"tiny media"


def _admin(live_client):
    ensure_topics(live_client)
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "admin")
    grant_role(live_client, registered.json()["user"]["id"], "teacher")
    return registered.json()["access_token"]


def _create_item(live_client, token: str, **overrides):
    body = {
        "topic_id": "daily_home",
        "ci_level": 0,
        "duration_seconds": 4,
        "media_type": "video",
        "visual_support": "high",
        "title_internal": "media",
    }
    body.update(overrides)
    response = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _publish(live_client, token: str, item_id: str):
    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200
    assert live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200


def test_upload_and_playback_dual_mode(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    item_id = _create_item(live_client, admin)

    uploaded = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("tiny.mp4", TINY_MP4, "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["playback_url"].startswith("http://")
    asset_id = uploaded.json()["id"]

    _publish(live_client, admin, item_id)
    listed = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    item = next(row for row in listed.json()["items"] if row["id"] == item_id)
    parsed = urlparse(item["playback_url"])
    assert parsed.query and "sig=" in parsed.query

    playback = live_client.get(
        f"/media/{asset_id}",
        headers={"Authorization": f"Bearer {learner}"},
    )
    assert playback.status_code == 200
    assert playback.headers["x-content-type-options"] == "nosniff"
    assert playback.content == TINY_MP4

    signed = live_client.get(f"{parsed.path}?{parsed.query}")
    assert signed.status_code == 200
    assert signed.content == TINY_MP4

    bad = live_client.get(f"/media/{asset_id}?exp=1&sig={'ab' * 32}")
    assert bad.status_code == 401


def test_learner_cannot_upload_and_empty_file_400(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    item_id = _create_item(live_client, admin, media_type="audio", visual_support="low", title_internal="empty")

    forbidden = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {learner}"},
        files={"file": ("learner.mp3", b"learner", "audio/mpeg")},
    )
    assert forbidden.status_code == 403

    empty = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("empty.mp3", b"", "audio/mpeg")},
    )
    assert empty.status_code == 400


def test_media_requires_auth(live_client):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin)
    uploaded = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("clip.mp4", TINY_MP4, "video/mp4")},
    )
    asset_id = uploaded.json()["id"]
    assert live_client.get(f"/media/{asset_id}").status_code == 401


@pytest.mark.asyncio
async def test_storage_port_unit(tmp_path):
    storage = LocalFilesystemStorage(tmp_path)

    # 1. Directory traversal rejected
    with pytest.raises(ValueError, match="Directory traversal detected"):
        storage._resolve("../outside.bin")

    # 2. Empty stream rejected
    async def empty_stream():
        if False:
            yield b""

    with pytest.raises(ValueError, match="File must not be empty"):
        await storage.stage_stream("test.part", empty_stream())
    assert not (tmp_path / "test.part").exists()

    # 3. Exceeding max_bytes rejected and part file removed
    async def big_stream():
        yield b"12345"
        yield b"67890"
        yield b"overflow"

    with pytest.raises(ValueError, match="File size exceeds limit"):
        await storage.stage_stream("big.part", big_stream(), max_bytes=10)
    assert not (tmp_path / "big.part").exists()

    # 4. Successful stage and promote
    async def good_stream():
        yield b"chunk1"
        yield b"chunk2"

    bytes_written = await storage.stage_stream("good.part", good_stream())
    assert bytes_written == 12
    assert (tmp_path / "good.part").exists()

    await storage.promote("good.part", "final/good.bin")
    assert not (tmp_path / "good.part").exists()
    assert (tmp_path / "final/good.bin").exists()
    meta = await storage.get_metadata("final/good.bin")
    assert meta.size == 12
    stream_iter = await storage.open_read("final/good.bin")
    chunks = [c async for c in stream_iter]
    assert b"".join(chunks) == b"chunk1chunk2"

    # 5. List keys
    keys = await storage.list_keys()
    assert "final/good.bin" in keys

    # 6. Delete
    assert await storage.delete("final/good.bin")
    assert not await storage.exists("final/good.bin")
    assert not await storage.delete("final/good.bin")


def test_publish_rejected_if_media_missing_from_storage(live_client):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="missing-media-file")
    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200

    # Insert media record in DB but delete the file from storage
    insert_media(live_client, item_id)
    storage = live_client.app.state.storage
    missing_file = storage.root / f"test/{item_id}.mp4"
    assert missing_file.exists()
    missing_file.unlink()

    published = live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert published.status_code == 400
    assert "missing from storage" in published.json()["message"]


def test_media_upload_db_failure_cleans_up_storage(live_client, monkeypatch):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="db-fail-cleanup")
    storage = live_client.app.state.storage

    from sqlalchemy.ext.asyncio import AsyncSession

    async def fail_commit(self):
        raise RuntimeError("Simulated DB commit error")

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="Simulated DB commit error"):
        live_client.post(
            f"/staff/catalog/{item_id}/media",
            headers={"Authorization": f"Bearer {admin}"},
            files={"file": ("test.mp4", TINY_MP4, "video/mp4")},
        )

    # Verify no .part or .bin files left in storage
    all_files = list(storage.root.rglob("*"))
    assert not any(f.is_file() for f in all_files)


def test_media_storage_failure_creates_no_db_row(live_client, monkeypatch):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="storage-fail-no-db")

    async def fail_stage(self, *args, **kwargs):
        raise RuntimeError("Disk full / stage error")

    monkeypatch.setattr(LocalFilesystemStorage, "stage_stream", fail_stage)

    with pytest.raises(RuntimeError, match="Disk full / stage error"):
        live_client.post(
            f"/staff/catalog/{item_id}/media",
            headers={"Authorization": f"Bearer {admin}"},
            files={"file": ("test.mp4", TINY_MP4, "video/mp4")},
        )

    async def count_assets():
        conn = await asyncpg.connect(live_client.app.state.settings.database_url)
        try:
            return await conn.fetchval(
                "SELECT count(*) FROM media_assets WHERE catalog_item_id = $1",
                item_id,
            )
        finally:
            await conn.close()

    count = asyncio.run(count_assets())
    assert count == 0


def test_orphan_reconciliation(live_client):
    storage = live_client.app.state.storage
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="orphan-test")

    # 1. Create an orphan file on disk (not in DB)
    orphan_key = "orphan_file.bin"
    orphan_path = storage.root / orphan_key
    orphan_path.write_bytes(b"orphan data")

    # 2. Insert media in DB but delete the file on disk (missing file)
    insert_media(live_client, item_id)
    missing_key = f"test/{item_id}.mp4"
    (storage.root / missing_key).unlink()

    from jplearn_api.db import create_engine_and_sessions

    async def _run_recon():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                rep_dry = await reconcile_orphans(session, storage, dry_run=True)
                assert orphan_key in rep_dry["orphan_storage_keys"]
                assert missing_key in rep_dry["missing_storage_keys"]
                assert len(rep_dry["deleted_storage_keys"]) == 0
                assert orphan_path.exists()
                import os
                import time
                now = time.time()
                old_mtime = now - (25 * 3600)
                os.utime(orphan_path, (old_mtime, old_mtime))
                rep_run = await reconcile_orphans(
                    session,
                    storage,
                    dry_run=False,
                    confirm_retention_exceeded=True,
                    now=now,
                )
                assert orphan_key in rep_run["deleted_storage_keys"]
                assert not orphan_path.exists()
        finally:
            await engine.dispose()

    asyncio.run(_run_recon())


# ==============================================================================
# R-04: Byte-Range Streaming Unit and Integration Tests
# ==============================================================================


def test_parse_byte_range_matrix():
    from jplearn_api.media_service import RangeNotSatisfiable, parse_byte_range

    total = 100

    # 1. Missing or empty header -> None (200)
    assert parse_byte_range(None, total) is None
    assert parse_byte_range("", total) is None
    assert parse_byte_range("   ", total) is None

    # 2. Non-byte range -> None (200)
    assert parse_byte_range("items=0-5", total) is None

    # 3. Multiple ranges -> None (200 per RFC 7233 §3.1 fallback)
    assert parse_byte_range("bytes=0-5, 10-15", total) is None

    # 4. Closed single range: bytes=0-1
    assert parse_byte_range("bytes=0-1", total) == (0, 1, 2)
    # bytes=4-7
    assert parse_byte_range("bytes=4-7", total) == (4, 7, 4)
    # Last byte
    assert parse_byte_range("bytes=99-99", total) == (99, 99, 1)

    # 5. Open-ended range: bytes=10-
    assert parse_byte_range("bytes=10-", total) == (10, 99, 90)

    # 6. Suffix range: bytes=-20
    assert parse_byte_range("bytes=-20", total) == (80, 99, 20)
    # Suffix larger than file -> entire file
    assert parse_byte_range("bytes=-150", total) == (0, 99, 100)

    # 7. Clamped end: bytes=50-200
    assert parse_byte_range("bytes=50-200", total) == (50, 99, 50)

    # 8. Unsatisfiable ranges -> raises RangeNotSatisfiable
    # Empty file
    with pytest.raises(RangeNotSatisfiable):
        parse_byte_range("bytes=0-0", 0)

    # Start >= total
    with pytest.raises(RangeNotSatisfiable):
        parse_byte_range("bytes=100-", total)

    with pytest.raises(RangeNotSatisfiable):
        parse_byte_range("bytes=105-110", total)

    # Inverted range start > end
    with pytest.raises(RangeNotSatisfiable):
        parse_byte_range("bytes=50-20", total)

    # Suffix <= 0
    with pytest.raises(RangeNotSatisfiable):
        parse_byte_range("bytes=-0", total)


@pytest.mark.asyncio
async def test_storage_adapters_open_read_range(tmp_path):
    from pathlib import Path
    from jplearn_api.storage import InMemoryStorage, LocalFilesystemStorage

    data = b"0123456789abcdefghijklmnopqrstuvwxyz" * 10
    total = len(data)

    fs_storage = LocalFilesystemStorage(tmp_path / "range_test")
    mem_storage = InMemoryStorage()

    # Seed data
    async def _stream():
        yield data

    await fs_storage.stage_stream("test.bin", _stream())
    await fs_storage.promote("test.bin", "final.bin")
    mem_storage.objects["final.bin"] = data

    for storage in [fs_storage, mem_storage]:
        # Range 0-4 (5 bytes)
        stream_iter = await storage.open_read_range("final.bin", 0, 5)
        chunks = [c async for c in stream_iter]
        assert b"".join(chunks) == data[0:5]

        # Offset 10, length 15
        stream_iter = await storage.open_read_range("final.bin", 10, 15)
        chunks = [c async for c in stream_iter]
        assert b"".join(chunks) == data[10:25]

        # Last byte
        stream_iter = await storage.open_read_range("final.bin", total - 1, 1)
        chunks = [c async for c in stream_iter]
        assert b"".join(chunks) == data[total - 1 :]


def test_media_stream_http_byte_ranges(live_client):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="range-stream-test")

    upload_resp = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("sample.mp4", TINY_MP4, "video/mp4")},
    )
    assert upload_resp.status_code == 201
    media_id = upload_resp.json()["id"]
    total_len = len(TINY_MP4)

    # 1. No Range header -> 200 OK, full body, Accept-Ranges: bytes
    r_full = live_client.get(f"/media/{media_id}", headers={"Authorization": f"Bearer {admin}"})
    assert r_full.status_code == 200
    assert r_full.headers.get("Accept-Ranges") == "bytes"
    assert r_full.headers.get("Content-Length") == str(total_len)
    assert r_full.headers.get("X-Content-Type-Options") == "nosniff"
    assert r_full.content == TINY_MP4

    # 2. Single byte range: bytes=0-1 -> 206 Partial Content, exact 2 bytes
    r_range2 = live_client.get(
        f"/media/{media_id}",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=0-1"},
    )
    assert r_range2.status_code == 206
    assert r_range2.headers.get("Accept-Ranges") == "bytes"
    assert r_range2.headers.get("Content-Range") == f"bytes 0-1/{total_len}"
    assert r_range2.headers.get("Content-Length") == "2"
    assert r_range2.content == TINY_MP4[0:2]

    # 3. Magic bytes seek: bytes=4-7 (ftyp)
    r_ftyp = live_client.get(
        f"/media/{media_id}",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=4-7"},
    )
    assert r_ftyp.status_code == 206
    assert r_ftyp.headers.get("Content-Range") == f"bytes 4-7/{total_len}"
    assert r_ftyp.headers.get("Content-Length") == "4"
    assert r_ftyp.content == b"ftyp"

    # 4. Open-ended range: bytes=10-
    r_open = live_client.get(
        f"/media/{media_id}",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=10-"},
    )
    assert r_open.status_code == 206
    assert r_open.headers.get("Content-Range") == f"bytes 10-{total_len - 1}/{total_len}"
    assert r_open.content == TINY_MP4[10:]

    # 5. Suffix range: bytes=-5 (last 5 bytes)
    r_suffix = live_client.get(
        f"/media/{media_id}",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=-5"},
    )
    assert r_suffix.status_code == 206
    assert r_suffix.headers.get("Content-Range") == f"bytes {total_len - 5}-{total_len - 1}/{total_len}"
    assert r_suffix.content == TINY_MP4[-5:]

    # 6. Unsatisfiable range: bytes=9999- -> 416 Range Not Satisfiable
    r_unsatisfiable = live_client.get(
        f"/media/{media_id}",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=9999-"},
    )
    assert r_unsatisfiable.status_code == 416
    assert r_unsatisfiable.headers.get("Content-Range") == f"bytes */{total_len}"

    # 7. Multiple ranges -> fallback to 200 with full entity
    r_multi = live_client.get(
        f"/media/{media_id}",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=0-1, 2-3"},
    )
    assert r_multi.status_code == 200
    assert r_multi.content == TINY_MP4


def test_hls_segment_http_byte_range(live_client):
    storage = live_client.app.state.storage
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="hls-range-test")

    # Upload base media
    upload_resp = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("sample.mp4", TINY_MP4, "video/mp4")},
    )
    media_id = upload_resp.json()["id"]

    # Manually create mock HLS files on storage: index.m3u8 and segment0.ts
    hls_dir = storage.root / "hls" / media_id
    hls_dir.mkdir(parents=True, exist_ok=True)
    (hls_dir / "index.m3u8").write_text("#EXTM3U\n#EXTINF:10.0,\nsegment0.ts\n#EXT-X-ENDLIST\n")
    ts_content = b"TS_PACKET_HEADER_DATA_1234567890"
    (hls_dir / "segment0.ts").write_bytes(ts_content)

    # Register HLS
    reg_resp = live_client.post(
        f"/staff/media/{media_id}/hls",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert reg_resp.status_code == 201

    # Request segment with Range: bytes=0-3
    r_seg = live_client.get(
        f"/media/{media_id}/hls/segment0.ts",
        headers={"Authorization": f"Bearer {admin}", "Range": "bytes=0-3"},
    )
    assert r_seg.status_code == 206
    assert r_seg.headers.get("Content-Range") == f"bytes 0-3/{len(ts_content)}"
    assert r_seg.headers.get("Content-Length") == "4"
    assert r_seg.content == ts_content[0:4]


