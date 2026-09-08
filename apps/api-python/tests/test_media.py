import asyncio
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import pytest

from helpers import ensure_topics, grant_role, insert_media, register
from jplearn_api.adapters.storage.local import LocalFilesystemStorage
from jplearn_api.entrypoints.cli.reconciliation import reconcile_orphans

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
    from helpers import approve_catalog

    assert (
        live_client.post(
            f"/staff/catalog/{item_id}/submit-qa",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )
    approve_catalog(live_client, token, item_id)
    assert (
        live_client.post(
            f"/staff/catalog/{item_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )


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
    assert (
        live_client.post(
            f"/staff/catalog/{item_id}/submit-qa",
            headers={"Authorization": f"Bearer {admin}"},
        ).status_code
        == 200
    )

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

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession

    async def fail_commit(self):
        raise IntegrityError("INSERT INTO media_assets", {}, Exception("constraint violation"))

    monkeypatch.setattr(AsyncSession, "commit", fail_commit)

    from jplearn_api.domain.errors import DeterministicAbortError

    with pytest.raises((IntegrityError, DeterministicAbortError), match="constraint violation"):
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

    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions

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
    from jplearn_api.adapters.storage.range_parser import RangeNotSatisfiable, parse_byte_range

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
    from jplearn_api.adapters.storage.local import InMemoryStorage, LocalFilesystemStorage

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


# ==============================================================================
# 8. R-07: Upload Cancellation & Object Lifecycle Cleanup
# ==============================================================================


@pytest.mark.asyncio
async def test_stage_stream_cancellation_cleans_up_part_file(tmp_path: Path):
    """R-07: Cancel during stage_stream must close handle and unlink .part file,
    preventing orphaned cancel.part files."""
    storage = LocalFilesystemStorage(tmp_path / "cancel_storage")
    temp_key = "test_cancel_artifact.part"
    part_path = storage.root / temp_key

    entered_stream = asyncio.Event()
    cancel_signal = asyncio.Event()

    async def pausing_stream():
        yield b"chunk_one_payload_data"
        entered_stream.set()
        await cancel_signal.wait()
        yield b"chunk_two_payload_data"

    task = asyncio.create_task(storage.stage_stream(temp_key, pausing_stream()))
    await entered_stream.wait()

    # Cancel the upload task while paused in stream
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Assert .part file was unlinked and does not remain on disk
    assert not part_path.exists(), f"Orphaned .part file remained on disk after cancellation: {part_path}"


async def _upload_media(
    session,
    settings,
    storage,
    catalog_item_id,
    file,
    *,
    _pre_commit_hook=None,
    _grace_seconds=None,
):
    from jplearn_api.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media
    from jplearn_api.bootstrap import create_media_signer

    def uow_factory():
        return SqlAlchemyUnitOfWork(session)

    signer = create_media_signer(settings)
    first_chunk = await file.read(64 * 1024)

    async def stream():
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    kwargs = {}
    if _grace_seconds is not None:
        kwargs["_grace_seconds"] = _grace_seconds

    return await handle_upload_media(
        catalog_item_id=catalog_item_id,
        first_chunk=first_chunk,
        stream=stream(),
        filename=file.filename or "",
        content_type=file.content_type,
        uow_factory=uow_factory,
        storage=storage,
        signer=signer,
        _pre_commit_hook=_pre_commit_hook,
        **kwargs,
    )


def test_upload_cancellation_before_commit_rolls_back_and_compensates(live_client):
    """R-07: Cancellation after promote but before DB commit must delete final object
    and rollback DB transaction."""
    from io import BytesIO

    from fastapi import UploadFile

    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="cancel-pre-commit")
    storage = live_client.app.state.storage

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                # Patch session.commit to simulate cancellation before commit proceeds
                real_add = session.add
                intercepted_asset_id = None

                def intercept_add(instance):
                    nonlocal intercepted_asset_id
                    if isinstance(instance, MediaAsset):
                        intercepted_asset_id = instance.id
                    return real_add(instance)

                session.add = intercept_add

                async def cancel_at_commit():
                    raise asyncio.CancelledError()

                with pytest.raises(asyncio.CancelledError):
                    await _upload_media(
                        session,
                        live_client.app.state.settings,
                        storage,
                        item_id,
                        upload_file,
                        _pre_commit_hook=cancel_at_commit,
                    )

                assert intercepted_asset_id is not None
                final_path = storage.root / f"{intercepted_asset_id}.bin"
                # Final key must be compensated (deleted) because transaction was not committed
                assert not final_path.exists(), "Final object remained in storage after cancelled commit!"

            # Verify using fresh connection that no orphan row exists in DB
            async with sessionmaker() as fresh_session:
                row = await fresh_session.get(MediaAsset, intercepted_asset_id)
                assert row is None, "Dangling MediaAsset row was created despite cancellation!"
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_upload_cancellation_during_commit_preserves_object_if_committed(live_client):
    """R-07: If transaction actually committed despite cancellation during wait,
    do NOT delete final object so DB row never points to missing file."""
    from io import BytesIO

    from fastapi import UploadFile

    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="cancel-post-commit")
    storage = live_client.app.state.storage

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                real_commit = session.commit

                async def commit_then_cancel():
                    await real_commit()
                    # Simulate cancellation received immediately after commit finishes
                    raise asyncio.CancelledError()

                session.commit = commit_then_cancel

                with pytest.raises(asyncio.CancelledError):
                    await _upload_media(session, live_client.app.state.settings, storage, item_id, upload_file)

            # Check in fresh session: DB row was committed
            async with sessionmaker() as fresh_session:
                result = await fresh_session.execute(
                    MediaAsset.__table__.select().where(MediaAsset.catalog_item_id == item_id)
                )
                row = result.fetchone()
                assert row is not None, "Expected committed row to exist"
                final_path = storage.root / row.storage_key
                # The file MUST be preserved because DB points to it!
                assert final_path.exists(), "Final object was deleted despite successful DB commit!"
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_upload_db_error_at_commit_compensates(live_client):
    """R-07: If DB pre-commit fails with an error, compensate by rolling back and deleting final object."""
    from io import BytesIO

    from fastapi import UploadFile

    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="db-err-commit")
    storage = live_client.app.state.storage

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                real_add = session.add
                intercepted_asset_id = None

                def intercept_add(instance):
                    nonlocal intercepted_asset_id
                    if isinstance(instance, MediaAsset):
                        intercepted_asset_id = instance.id
                    return real_add(instance)

                session.add = intercept_add

                async def error_at_commit():
                    raise RuntimeError("Simulated DB commit failure")

                with pytest.raises(RuntimeError, match="Simulated DB commit failure"):
                    await _upload_media(
                        session,
                        live_client.app.state.settings,
                        storage,
                        item_id,
                        upload_file,
                        _pre_commit_hook=error_at_commit,
                    )

                assert intercepted_asset_id is not None
                final_path = storage.root / f"{intercepted_asset_id}.bin"
                assert not final_path.exists(), "Final object remained in storage after failed commit!"
        finally:
            await engine.dispose()

    asyncio.run(_run())


# ==============================================================================
# 9. R-07/B: Five Mandatory COMMIT Outcome & Recovery Tests (Real PostgreSQL)
# ==============================================================================


def test_upload_outcome_1_pre_commit_cancellation_compensates(live_client):
    """Scenario 1: Cancellation before commit -> rollback confirmed -> compensate object."""
    from io import BytesIO

    from fastapi import UploadFile

    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="scen1-pre-commit")
    storage = live_client.app.state.storage

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                intercepted_asset_id = None
                real_add = session.add

                def intercept_add(instance):
                    nonlocal intercepted_asset_id
                    if isinstance(instance, MediaAsset):
                        intercepted_asset_id = instance.id
                    return real_add(instance)

                session.add = intercept_add

                async def cancel_pre_commit():
                    raise asyncio.CancelledError()

                with pytest.raises(asyncio.CancelledError):
                    await _upload_media(
                        session,
                        live_client.app.state.settings,
                        storage,
                        item_id,
                        upload_file,
                        _pre_commit_hook=cancel_pre_commit,
                    )

                assert intercepted_asset_id is not None
                final_path = storage.root / f"{intercepted_asset_id}.bin"
                assert not final_path.exists(), "Object was not compensated after pre-commit cancellation!"

            async with sessionmaker() as fresh_session:
                row = await fresh_session.get(MediaAsset, intercepted_asset_id)
                assert row is None, "Row exists in DB despite rollback!"
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_upload_outcome_2_commit_in_flight_cancelled_preserves_object_and_logs(live_client, monkeypatch):
    """Scenario 2: Cancellation while COMMIT in-flight -> outcome unknown -> preserve object, log recovery."""
    from io import BytesIO

    from fastapi import UploadFile

    import jplearn_api.application.handlers.media as media_handlers
    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="scen2-in-flight")
    storage = live_client.app.state.storage

    logged_warnings = []
    real_warning = media_handlers.logger.warning

    def capture_warning(msg, *args, **kwargs):
        logged_warnings.append((msg, kwargs.get("extra", {})))
        return real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(media_handlers.logger, "warning", capture_warning)
    monkeypatch.setattr(media_handlers, "COMMIT_CANCELLATION_GRACE_SECONDS", 0.05)

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                intercepted_asset_id = None
                real_add = session.add

                def intercept_add(instance):
                    nonlocal intercepted_asset_id
                    if isinstance(instance, MediaAsset):
                        intercepted_asset_id = instance.id
                    return real_add(instance)

                session.add = intercept_add

                # Simulate commit that hangs / is in-flight when cancelled
                commit_entered = asyncio.Event()

                async def hanging_commit():
                    commit_entered.set()
                    try:
                        await asyncio.sleep(10.0)
                    except asyncio.CancelledError:
                        pass

                session.commit = hanging_commit

                upload_task = asyncio.create_task(
                    _upload_media(session, live_client.app.state.settings, storage, item_id, upload_file)
                )

                await commit_entered.wait()
                upload_task.cancel()

                with pytest.raises(asyncio.CancelledError):
                    await upload_task

                assert intercepted_asset_id is not None
                final_path = storage.root / f"{intercepted_asset_id}.bin"
                # Object MUST be preserved because commit outcome is unknown
                assert final_path.exists(), "Object was erroneously deleted when commit was in-flight!"

                # Structured recovery signal must be logged
                recovery_logs = [w for w in logged_warnings if w[0] == "media_upload_commit_outcome_unknown"]
                assert len(recovery_logs) >= 1
                assert recovery_logs[0][1].get("asset_id") == intercepted_asset_id

                # Cleanup test file
                final_path.unlink(missing_ok=True)
        finally:
            await engine.dispose()

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_upload_does_not_rollback_while_cancelled_commit_is_still_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-07/B: rollback starts only after the COMMIT task reaches terminal state."""
    from io import BytesIO
    from types import SimpleNamespace

    from fastapi import UploadFile

    import jplearn_api.application.handlers.media as media_handlers

    commit_entered = asyncio.Event()
    commit_release = asyncio.Event()
    rollback_called = asyncio.Event()
    commit_active = False
    rollback_raced_commit = False

    class BarrierSession:
        async def get(self, *args, **kwargs):
            return object()

        def add(self, instance) -> None:
            pass

        async def commit(self) -> None:
            nonlocal commit_active
            commit_active = True
            commit_entered.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await commit_release.wait()
            finally:
                commit_active = False

        async def rollback(self) -> None:
            nonlocal rollback_raced_commit
            rollback_raced_commit = commit_active
            rollback_called.set()

    class MemoryStorage:
        async def inspect_media(self, key):
            from jplearn_api.application.ports.media_probe import MediaInspection

            return MediaInspection(3_600_000, "fixture-checksum")

        async def stage_stream(self, key, stream) -> int:
            total = 0
            async for chunk in stream:
                total += len(chunk)
            return total

        async def promote(self, temp_key, final_key) -> None:
            pass

        async def delete(self, key) -> bool:
            return True

    monkeypatch.setattr(media_handlers, "COMMIT_CANCELLATION_GRACE_SECONDS", 0.01)
    upload_file = UploadFile(
        filename="sample.mp4",
        file=BytesIO(TINY_MP4),
        headers={"content-type": "video/mp4"},
    )
    task = asyncio.create_task(
        _upload_media(
            BarrierSession(),
            SimpleNamespace(api_public_url="http://localhost"),
            MemoryStorage(),
            "catalog-id",
            upload_file,
        )
    )

    await asyncio.wait_for(commit_entered.wait(), timeout=5)
    rollback_called.clear()
    task.cancel()
    try:
        await asyncio.sleep(0.05)

        assert rollback_called.is_set() is False
        assert task.done() is False
    finally:
        commit_release.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert rollback_called.is_set() is True
    assert rollback_raced_commit is False


def test_upload_outcome_3_server_commit_response_lost_preserves_object(live_client, monkeypatch):
    """Scenario 3: Server committed, but client received network/unknown error -> preserve object."""
    from io import BytesIO

    from fastapi import UploadFile

    import jplearn_api.application.handlers.media as media_handlers
    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="scen3-response-lost")
    storage = live_client.app.state.storage

    logged_warnings = []
    real_warning = media_handlers.logger.warning

    def capture_warning(msg, *args, **kwargs):
        logged_warnings.append((msg, kwargs.get("extra", {})))
        return real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(media_handlers.logger, "warning", capture_warning)

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                intercepted_asset_id = None
                real_add = session.add

                def intercept_add(instance):
                    nonlocal intercepted_asset_id
                    if isinstance(instance, MediaAsset):
                        intercepted_asset_id = instance.id
                    return real_add(instance)

                session.add = intercept_add

                real_commit = session.commit

                async def commit_then_error():
                    await real_commit()
                    # Simulate disconnect or response loss after commit reached server
                    raise ConnectionResetError("Connection lost after COMMIT dispatched")

                session.commit = commit_then_error

                with pytest.raises(ConnectionResetError):
                    await _upload_media(session, live_client.app.state.settings, storage, item_id, upload_file)

                assert intercepted_asset_id is not None
                final_path = storage.root / f"{intercepted_asset_id}.bin"
                # Object MUST be preserved so DB row does not point to missing object
                assert final_path.exists(), "Object was deleted despite DB transaction committing!"

                # Verify via fresh connection that DB row DOES exist in PostgreSQL!
                async with sessionmaker() as fresh_session:
                    row = await fresh_session.get(MediaAsset, intercepted_asset_id)
                    assert row is not None, "Expected committed row to exist in PostgreSQL!"

                # Structured recovery signal logged
                recovery_logs = [w for w in logged_warnings if w[0] == "media_upload_commit_outcome_unknown"]
                assert len(recovery_logs) >= 1
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_upload_outcome_4_rollback_failure_preserves_object_and_logs(live_client, monkeypatch):
    """Scenario 4: Rollback fails with an exception -> outcome unknown -> preserve object, log recovery."""
    from io import BytesIO

    from fastapi import UploadFile

    import jplearn_api.application.handlers.media as media_handlers
    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="scen4-rb-fail")
    storage = live_client.app.state.storage

    logged_warnings = []
    real_warning = media_handlers.logger.warning

    def capture_warning(msg, *args, **kwargs):
        logged_warnings.append((msg, kwargs.get("extra", {})))
        return real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(media_handlers.logger, "warning", capture_warning)

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                intercepted_asset_id = None
                real_add = session.add

                def intercept_add(instance):
                    nonlocal intercepted_asset_id
                    if isinstance(instance, MediaAsset):
                        intercepted_asset_id = instance.id
                    return real_add(instance)

                session.add = intercept_add

                rollback_count = 0
                real_rollback = session.rollback

                async def fail_rollback():
                    nonlocal rollback_count
                    rollback_count += 1
                    if rollback_count > 1:
                        raise RuntimeError("Rollback connection error")
                    return await real_rollback()

                session.rollback = fail_rollback

                async def error_pre_commit():
                    raise RuntimeError("Pre-commit validation error")

                with pytest.raises(RuntimeError, match="Pre-commit validation error"):
                    await _upload_media(
                        session,
                        live_client.app.state.settings,
                        storage,
                        item_id,
                        upload_file,
                        _pre_commit_hook=error_pre_commit,
                    )

                assert intercepted_asset_id is not None
                final_path = storage.root / f"{intercepted_asset_id}.bin"
                # Because rollback failed, outcome is UNKNOWN -> preserve object
                assert final_path.exists(), "Object was deleted despite rollback failure!"

                recovery_logs = [w for w in logged_warnings if w[0] == "media_upload_commit_outcome_unknown"]
                assert len(recovery_logs) >= 1
                assert "rollback_failed" in recovery_logs[0][1].get("reason", "")

                # Cleanup test file
                final_path.unlink(missing_ok=True)
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_upload_outcome_5_post_commit_cancellation_preserves_object(live_client):
    """Scenario 5: Post-commit cancellation -> transaction committed -> preserve object."""
    from io import BytesIO

    from fastapi import UploadFile

    from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
    from jplearn_api.adapters.persistence.models import MediaAsset

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="scen5-post-commit")
    storage = live_client.app.state.storage

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            async with sessionmaker() as session:
                upload_file = UploadFile(
                    filename="sample.mp4",
                    file=BytesIO(TINY_MP4),
                    headers={"content-type": "video/mp4"},
                )

                real_commit = session.commit

                async def commit_then_cancel():
                    await real_commit()
                    # Simulates client disconnect immediately after server commits
                    raise asyncio.CancelledError()

                session.commit = commit_then_cancel

                with pytest.raises(asyncio.CancelledError):
                    await _upload_media(session, live_client.app.state.settings, storage, item_id, upload_file)

            async with sessionmaker() as fresh_session:
                result = await fresh_session.execute(
                    MediaAsset.__table__.select().where(MediaAsset.catalog_item_id == item_id)
                )
                row = result.fetchone()
                assert row is not None, "Expected committed row to exist in DB"
                final_path = storage.root / row.storage_key
                assert final_path.exists(), "Object was deleted despite commit completing!"
        finally:
            await engine.dispose()

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_upload_repo_add_failure_after_promote_rolls_back_and_compensates():
    """G1: Fault injection into repo.add() after promote must rollback UoW and delete final object."""
    from fakes import FakeMediaRepository, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media

    FakeUnitOfWork()
    media_repo = FakeMediaRepository()
    media_repo.catalog_items.add("cat-item-1")
    storage = FakeStoragePort()

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    async def fail_add(asset):
        raise RuntimeError("Database connection dropped during repo.add")

    media_repo.add = fail_add

    from fakes import FakeMediaUrlSigner, create_fake_uow_factory

    signer = FakeMediaUrlSigner()

    with pytest.raises(RuntimeError, match="Database connection dropped during repo.add"):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=create_fake_uow_factory(media=media_repo),
            storage=storage,
            signer=signer,
        )

    # Invariant: final object must NOT remain in storage!
    assert len(storage.keys) == 0, f"Final promoted object leaked in storage: {storage.keys}"


@pytest.mark.asyncio
async def test_upload_recheck_catalog_query_error_compensates_storage():
    """R1 regression test: When catalog recheck query raises after promote,
    write UoW rolls back, rollback is confirmed, and final object is deleted from storage.
    """
    from fakes import FakeMediaRepository, FakeMediaUrlSigner, FakeStoragePort, create_fake_uow_factory
    from jplearn_api.application.handlers.media import handle_upload_media

    media_repo = FakeMediaRepository()
    media_repo.catalog_items.add("cat-item-1")
    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    call_count = 0
    real_catalog_exists = media_repo.catalog_item_exists

    async def flaky_catalog_exists(item_id: str) -> bool:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Scope 1 (preflight) succeeds
            return await real_catalog_exists(item_id)
        # Scope 3 (write recheck) raises DB error!
        raise RuntimeError("Simulated database failure during catalog recheck query")

    media_repo.catalog_item_exists = flaky_catalog_exists

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    with pytest.raises(RuntimeError, match="Simulated database failure during catalog recheck query"):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=create_fake_uow_factory(media=media_repo),
            storage=storage,
            signer=signer,
        )

    # Invariant: final object must NOT remain in storage!
    assert len(storage.keys) == 0, f"Final promoted object leaked in storage: {storage.keys}"


@pytest.mark.asyncio
async def test_upload_repeated_cancellation_preserves_cleanup_and_deletes_object():
    """C1 reproducer: Query recheck is cancelled (1st cancel), and then rollback cleanup
    is cancelled again (2nd cancel).
    Invariant: Rollback is confirmed -> final object MUST be deleted from storage!
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    uow1 = FakeUnitOfWork()
    uow1.media.catalog_items.add("cat-item-1")

    uow2 = FakeUnitOfWork()
    uow2.media.catalog_items.add("cat-item-1")

    recheck_barrier = asyncio.Event()
    rollback_barrier = asyncio.Event()
    rollback_proceed = asyncio.Event()

    real_catalog_exists = uow2.media.catalog_item_exists

    async def cancelling_catalog_exists(item_id: str) -> bool:
        recheck_barrier.set()
        # Wait until cancelled
        await asyncio.sleep(100)
        return await real_catalog_exists(item_id)

    uow2.media.catalog_item_exists = cancelling_catalog_exists

    real_rollback = uow2.rollback

    async def barrier_rollback() -> None:
        rollback_barrier.set()
        await rollback_proceed.wait()
        await real_rollback()

    uow2.rollback = barrier_rollback

    scopes = [uow1, uow2]

    def uow_factory():
        return scopes.pop(0)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    upload_task = asyncio.create_task(
        handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
        )
    )

    # 1. Wait until recheck in Scope 3 is entered
    await recheck_barrier.wait()

    # 2. Trigger 1st cancellation (at recheck query)
    upload_task.cancel()

    # 3. Wait until cleanup rollback begins
    await rollback_barrier.wait()

    # 4. Trigger 2nd cancellation (while rollback cleanup is in-flight)
    upload_task.cancel()
    rollback_proceed.set()

    # 5. Wait for upload_task to terminate
    with pytest.raises(asyncio.CancelledError):
        await upload_task

    # Invariant: write_uow rollback is confirmed, so final promoted object MUST NOT leak in storage!
    assert uow2.rolled_back is True, "Write UoW must be rolled back"
    assert len(storage.keys) == 0, f"Final object leaked in storage after repeated cancellation: {storage.keys}"


@pytest.mark.asyncio
async def test_upload_cancellation_during_storage_delete_completes_cleanup_and_no_orphan_task():
    """C1 fault matrix: Cancellation received while storage delete is in-flight
    does not abandon cleanup task; cleanup completes and final object is removed.
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    uow1 = FakeUnitOfWork()
    uow1.media.catalog_items.add("cat-item-1")

    uow2 = FakeUnitOfWork()
    uow2.media.catalog_items.add("cat-item-1")

    recheck_barrier = asyncio.Event()
    recheck_proceed = asyncio.Event()
    real_exists = uow2.media.catalog_item_exists

    async def barrier_exists(catalog_item_id):
        recheck_barrier.set()
        await recheck_proceed.wait()
        return await real_exists(catalog_item_id)

    uow2.media.catalog_item_exists = barrier_exists

    delete_barrier = asyncio.Event()
    delete_proceed = asyncio.Event()
    real_delete = storage.delete

    async def barrier_delete(key):
        delete_barrier.set()
        await delete_proceed.wait()
        return await real_delete(key)

    storage.delete = barrier_delete

    scopes = [uow1, uow2]

    def uow_factory():
        return scopes.pop(0)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    upload_task = asyncio.create_task(
        handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
        )
    )

    # 1. Wait until recheck in Scope 3 is entered and trigger 1st cancellation
    await recheck_barrier.wait()
    upload_task.cancel()
    recheck_proceed.set()

    # 2. Wait until storage delete begins
    await delete_barrier.wait()

    # 3. Trigger 2nd cancellation while storage delete is actively in-flight
    upload_task.cancel()
    delete_proceed.set()

    # 4. Wait for upload_task to terminate
    with pytest.raises(asyncio.CancelledError):
        await upload_task

    # Invariant: storage delete completed, no leak
    assert uow2.rolled_back is True, "Write UoW must be rolled back"
    assert len(storage.keys) == 0, f"Final object leaked: {storage.keys}"


@pytest.mark.asyncio
async def test_upload_triple_cancellation_preserves_original_cancelled_error():
    """C1 fault matrix: Triple repeated cancellation across recheck, rollback,
    and storage delete does not cause concurrency error, unhandled exception, or storage leak.
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    uow1 = FakeUnitOfWork()
    uow1.media.catalog_items.add("cat-item-1")

    uow2 = FakeUnitOfWork()
    uow2.media.catalog_items.add("cat-item-1")

    recheck_barrier = asyncio.Event()
    recheck_proceed = asyncio.Event()
    real_exists = uow2.media.catalog_item_exists

    async def barrier_exists(catalog_item_id):
        recheck_barrier.set()
        await recheck_proceed.wait()
        return await real_exists(catalog_item_id)

    uow2.media.catalog_item_exists = barrier_exists

    rollback_barrier = asyncio.Event()
    rollback_proceed = asyncio.Event()
    real_rollback = uow2.rollback

    async def barrier_rollback():
        rollback_barrier.set()
        await rollback_proceed.wait()
        await real_rollback()

    uow2.rollback = barrier_rollback

    delete_barrier = asyncio.Event()
    delete_proceed = asyncio.Event()
    real_delete = storage.delete

    async def barrier_delete(key):
        delete_barrier.set()
        await delete_proceed.wait()
        return await real_delete(key)

    storage.delete = barrier_delete

    scopes = [uow1, uow2]

    def uow_factory():
        return scopes.pop(0)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    upload_task = asyncio.create_task(
        handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
        )
    )

    # 1. Cancel at recheck
    await recheck_barrier.wait()
    upload_task.cancel()
    recheck_proceed.set()

    # 2. Cancel at rollback
    await rollback_barrier.wait()
    upload_task.cancel()
    rollback_proceed.set()

    # 3. Cancel at storage delete
    await delete_barrier.wait()
    upload_task.cancel()
    delete_proceed.set()

    with pytest.raises(asyncio.CancelledError):
        await upload_task

    assert uow2.rolled_back is True
    assert len(storage.keys) == 0


@pytest.mark.asyncio
async def test_upload_rollback_drain_timeout_sets_outcome_unknown_and_retains_object(monkeypatch):
    """C1 fault matrix: When rollback cleanup hangs and exceeds grace budget,
    coordinator marks outcome as outcome_unknown, retains final object for recovery,
    and logs structured warning with task state.
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media, logger

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    uow1 = FakeUnitOfWork()
    uow1.media.catalog_items.add("cat-item-1")

    uow2 = FakeUnitOfWork()
    uow2.media.catalog_items.add("cat-item-1")

    recheck_barrier = asyncio.Event()
    real_exists = uow2.media.catalog_item_exists

    async def barrier_exists(catalog_item_id):
        recheck_barrier.set()
        await asyncio.sleep(100)  # Hang indefinitely until cancelled
        return await real_exists(catalog_item_id)

    uow2.media.catalog_item_exists = barrier_exists

    # Rollback also hangs indefinitely
    async def hanging_rollback():
        await asyncio.sleep(100)

    uow2.rollback = hanging_rollback

    scopes = [uow1, uow2]

    def uow_factory():
        return scopes.pop(0)

    logged_warnings = []
    real_warning = logger.warning

    def capture_warning(msg, *args, **kwargs):
        logged_warnings.append((msg, kwargs.get("extra", {})))
        return real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(logger, "warning", capture_warning)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    upload_task = asyncio.create_task(
        handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
            _grace_seconds=0.05,
        )
    )

    await recheck_barrier.wait()
    upload_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await upload_task

    # Invariant: Drain timed out, so outcome is unknown, final object is retained
    assert len(storage.keys) == 1, f"Object must be retained when rollback times out: {storage.keys}"
    unknown_warnings = [w for w in logged_warnings if w[0] == "media_upload_commit_outcome_unknown"]
    assert len(unknown_warnings) >= 1
    assert "drain_timeout" in unknown_warnings[0][1].get("task_state", "")


@pytest.mark.asyncio
async def test_upload_write_uow_enter_failure_compensates_storage():
    """R1 regression test: When write UoW __aenter__ raises after promote,
    final object is deleted from storage and original exception is preserved.
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    uow1 = FakeUnitOfWork()
    uow1.media.catalog_items.add("cat-item-1")

    class FailingEnterUoW(FakeUnitOfWork):
        async def __aenter__(self):
            raise ConnectionError("Failed to acquire DB session on enter")

    uow2 = FailingEnterUoW()
    scopes = [uow1, uow2]

    def uow_factory():
        return scopes.pop(0)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    with pytest.raises(ConnectionError, match="Failed to acquire DB session on enter"):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
        )

    # Invariant: promoted object was cleaned up from storage!
    assert len(storage.keys) == 0, f"Promoted object leaked: {storage.keys}"


@pytest.mark.asyncio
async def test_upload_rollback_failure_retains_storage_object_and_logs_unknown_outcome(monkeypatch):
    """R1 fault matrix: When rollback fails after error, outcome is unknown,
    final object is retained for safety, and warning is logged.
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media, logger

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    uow1 = FakeUnitOfWork()
    uow1.media.catalog_items.add("cat-item-1")

    uow2 = FakeUnitOfWork()
    uow2.media.catalog_items.add("cat-item-1")

    async def fail_add(asset):
        raise RuntimeError("Database error on add")

    async def fail_rollback():
        raise RuntimeError("DB network down during rollback")

    uow2.media.add = fail_add
    uow2.rollback = fail_rollback

    scopes = [uow1, uow2]

    def uow_factory():
        return scopes.pop(0)

    logged_warnings = []
    real_warning = logger.warning

    def capture_warning(msg, *args, **kwargs):
        logged_warnings.append((msg, kwargs.get("extra", {})))
        return real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(logger, "warning", capture_warning)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    with pytest.raises(RuntimeError, match="Database error on add"):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
        )

    # Invariant: Because rollback failed, outcome is UNKNOWN! Final object MUST be retained.
    assert len(storage.keys) == 1, f"Expected final object retained on unknown rollback, got {storage.keys}"
    unknown_warnings = [w for w in logged_warnings if w[0] == "media_upload_commit_outcome_unknown"]
    assert len(unknown_warnings) >= 1
    assert "rollback_failed" in unknown_warnings[0][1].get("reason", "")


@pytest.mark.asyncio
async def test_upload_pre_commit_storage_delete_failure_preserves_original_exception_and_logs_warning(monkeypatch):
    """G1: If storage.delete fails during pre-commit compensation, original error is preserved and warning is logged."""
    from fakes import FakeMediaRepository, FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media, logger

    media_repo = FakeMediaRepository()
    media_repo.catalog_items.add("cat-item-1")
    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    logged_warnings = []
    real_warning = logger.warning

    def capture_warning(msg, *args, **kwargs):
        logged_warnings.append((msg, kwargs.get("extra", {})))
        return real_warning(msg, *args, **kwargs)

    monkeypatch.setattr(logger, "warning", capture_warning)

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    async def fail_hook():
        raise ValueError("Specific pre-commit validation failure")

    async def fail_delete(key):
        raise PermissionError("Storage permission denied on unlink")

    storage.delete = fail_delete

    uow = FakeUnitOfWork(media_repo)
    with pytest.raises(ValueError, match="Specific pre-commit validation failure"):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=lambda: uow,
            storage=storage,
            signer=signer,
            _pre_commit_hook=fail_hook,
        )

    assert uow.rolled_back is True
    cleanup_warnings = [w for w in logged_warnings if w[0] == "media_cleanup_failed"]
    assert len(cleanup_warnings) == 1
    assert "PermissionError" in cleanup_warnings[0][1].get("reason", "")
    assert "secret" not in str(cleanup_warnings[0][1])


def test_upload_byte_stream_barrier_releases_db_connection(live_client, live_database_url):
    """V1 barrier test: verify that during byte streaming, DB connection has been returned to pool
    and zero open transactions exist in pg_stat_activity for the request.
    """
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="barrier-test")
    storage = live_client.app.state.storage

    barrier_active = asyncio.Event()
    barrier_release = asyncio.Event()
    inspected_tx_count = -1

    async def _run():
        nonlocal inspected_tx_count
        from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
        from jplearn_api.application.handlers.media import handle_upload_media
        from jplearn_api.bootstrap import create_uow_factory

        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        uow_factory = create_uow_factory(sessionmaker)

        async def stream_with_barrier():
            barrier_active.set()
            await barrier_release.wait()
            yield b"streaming payload chunk"

        async def staging_barrier():
            # In Scope 2: query pg_stat_activity using an isolated connection
            conn = await asyncpg.connect(live_database_url)
            try:
                # Count open or idle-in-transaction connections on jplearn_test
                rows = await conn.fetch(
                    """
                    SELECT pid, state, query, xact_start
                    FROM pg_stat_activity
                    WHERE datname = 'jplearn_test'
                      AND pid != pg_backend_pid()
                      AND state in ('idle in transaction', 'active')
                    """
                )
                nonlocal inspected_tx_count
                inspected_tx_count = len(rows)
            finally:
                await conn.close()

        from jplearn_api.bootstrap import create_media_signer

        signer = create_media_signer(live_client.app.state.settings)
        first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
        dto = await handle_upload_media(
            catalog_item_id=item_id,
            first_chunk=first_chunk,
            stream=stream_with_barrier(),
            filename="barrier.mp4",
            content_type="video/mp4",
            uow_factory=uow_factory,
            storage=storage,
            signer=signer,
            _staging_barrier=staging_barrier,
        )

        await engine.dispose()
        return dto

    async def _coordinator():
        upload_task = asyncio.create_task(_run())
        await barrier_active.wait()
        barrier_release.set()
        return await upload_task

    dto = asyncio.run(_coordinator())
    assert inspected_tx_count == 0, f"Expected 0 active transactions during byte staging, found {inspected_tx_count}"
    assert dto.id is not None
    assert (storage.root / f"{dto.id}.bin").exists()


def test_upload_catalog_deleted_between_preflight_and_write_compensates(live_client, live_database_url):
    """V1 compensation test: when catalog item is deleted between preflight and write,
    write UoW rolls back, deletes promoted file from storage, and leaves no orphan asset.
    """
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin, title_internal="deleted-item-test")
    storage = live_client.app.state.storage

    async def _run():
        from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
        from jplearn_api.application.handlers.media import handle_upload_media
        from jplearn_api.bootstrap import create_media_signer, create_uow_factory
        from jplearn_api.domain.errors import EntityNotFoundError

        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        uow_factory = create_uow_factory(sessionmaker)
        signer = create_media_signer(live_client.app.state.settings)

        async def delete_catalog_during_staging():
            # Delete the catalog item between Scope 1 (preflight) and Scope 3 (write)
            conn = await asyncpg.connect(live_database_url)
            try:
                await conn.execute("DELETE FROM catalog_items WHERE id = $1", item_id)
            finally:
                await conn.close()

        first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

        async def payload_stream():
            yield b"payload bytes for media item"

        with pytest.raises(EntityNotFoundError, match="Catalog item not found"):
            await handle_upload_media(
                catalog_item_id=item_id,
                first_chunk=first_chunk,
                stream=payload_stream(),
                filename="deleted_cat.mp4",
                content_type="video/mp4",
                uow_factory=uow_factory,
                storage=storage,
                signer=signer,
                _staging_barrier=delete_catalog_during_staging,
            )

        # Verify DB has 0 media assets for this deleted catalog item
        conn = await asyncpg.connect(live_database_url)
        try:
            row_count = await conn.fetchval(
                "SELECT count(*) FROM media_assets WHERE catalog_item_id = $1",
                item_id,
            )
            assert row_count == 0
        finally:
            await conn.close()
        await engine.dispose()

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_upload_uow_factory_scopes_and_repository_identity():
    """R2 test: handle_upload_media invokes uow_factory for each scope, uses active scope repos,
    and rollback of write scope does not mutate or erase committed state from earlier scopes.
    """
    from fakes import FakeMediaUrlSigner, FakeStoragePort, FakeUnitOfWork
    from jplearn_api.application.handlers.media import handle_upload_media

    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    created_uows = []

    def tracking_factory():
        uow = FakeUnitOfWork()
        uow.media.catalog_items.add("cat-item-1")
        created_uows.append(uow)
        return uow

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    def fail_hook():
        raise RuntimeError("Abort in scope 3")

    with pytest.raises(RuntimeError, match="Abort in scope 3"):
        await handle_upload_media(
            catalog_item_id="cat-item-1",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=tracking_factory,
            storage=storage,
            signer=signer,
            _pre_commit_hook=fail_hook,
        )

    # 1. Verify exactly 2 UoW instances were created (Scope 1 preflight, Scope 3 write)
    assert len(created_uows) == 2, f"Expected 2 scoped UoW instances, got {len(created_uows)}"
    scope1_uow, scope3_uow = created_uows

    # 2. Verify instance identity: Scope 1 is NOT Scope 3
    assert scope1_uow is not scope3_uow, "Expected distinct UoW instances for distinct scopes"

    # 3. Scope 1 was read-only and exited cleanly; Scope 3 was rolled back
    assert scope3_uow.rolled_back is True, "Scope 3 UoW must be rolled back on abort"
    assert len(storage.keys) == 0, "Storage must be compensated on Scope 3 abort"


@pytest.mark.asyncio
async def test_upload_http_barrier_releases_connection_and_pool_checkout(live_database_url, monkeypatch):
    """R2 HTTP test: actual HTTP multipart upload through auth dependency and storage barrier.
    Verifies that:
    1. Auth/preflight connection is returned to pool before byte streaming.
    2. engine.pool.checkedout() is exactly 0 during byte streaming.
    3. pg_stat_activity has 0 active transactions for the request.
    4. HTTP response returns 201 Created.
    """
    import tempfile
    import uuid

    import httpx

    from conftest import _settings
    from jplearn_api.entrypoints.http.app import create_app

    with tempfile.TemporaryDirectory() as storage_dir:
        settings = _settings(live_database_url)
        settings.storage_root = storage_dir
        app = create_app(settings)

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                conn = await asyncpg.connect(live_database_url)
                try:
                    for topic_id in ("daily_home", "food", "body", "go_somewhere", "nature", "people"):
                        await conn.execute(
                            "INSERT INTO topics (id, label_internal) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
                            topic_id,
                            topic_id,
                        )
                finally:
                    await conn.close()

                reg_res = await client.post(
                    "/auth/register",
                    json={"email": f"httpbarrier_{uuid.uuid4().hex[:8]}@example.com", "password": "password10"},
                )
                assert reg_res.status_code == 201, reg_res.text
                user_info = reg_res.json()
                admin_token = user_info["access_token"]
                user_id = user_info["user"]["id"]

                conn = await asyncpg.connect(live_database_url)
                try:
                    for role in ("admin", "teacher"):
                        await conn.execute(
                            'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
                            user_id,
                            role,
                        )
                finally:
                    await conn.close()

                cat_res = await client.post(
                    "/staff/catalog",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={
                        "topic_id": "daily_home",
                        "ci_level": 0,
                        "duration_seconds": 4,
                        "media_type": "video",
                        "visual_support": "high",
                        "title_internal": "http-barrier-test",
                    },
                )
                assert cat_res.status_code == 201, cat_res.text
                item_id = cat_res.json()["id"]

                storage = app.state.storage
                engine = app.state.engine
                barrier_active = asyncio.Event()
                barrier_release = asyncio.Event()
                inspected_checked_out = -1
                inspected_tx_count = -1

                real_stage_stream = storage.stage_stream

                async def barrier_stage_stream(key, stream):
                    barrier_active.set()
                    await barrier_release.wait()
                    return await real_stage_stream(key, stream)

                monkeypatch.setattr(storage, "stage_stream", barrier_stage_stream)

                valid_payload = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"X" * 1024

                upload_task = asyncio.create_task(
                    client.post(
                        f"/staff/catalog/{item_id}/media",
                        headers={"Authorization": f"Bearer {admin_token}"},
                        files={"file": ("video.mp4", valid_payload, "video/mp4")},
                    )
                )

                await barrier_active.wait()

                inspected_checked_out = engine.pool.checkedout()

                conn = await asyncpg.connect(live_database_url)
                try:
                    rows = await conn.fetch(
                        """
                        SELECT pid, state, query
                        FROM pg_stat_activity
                        WHERE datname = 'jplearn_test'
                          AND pid != pg_backend_pid()
                          AND state in ('idle in transaction', 'active')
                        """
                    )
                    inspected_tx_count = len(rows)
                finally:
                    await conn.close()

                barrier_release.set()
                res = await upload_task

                assert inspected_checked_out == 0, f"Expected 0 checked out connections, got {inspected_checked_out}"
                assert inspected_tx_count == 0, f"Expected 0 active transactions, got {inspected_tx_count}"
                assert res.status_code == 201, f"Expected 201 Created, got {res.status_code}: {res.text}"
                data = res.json()
                assert (storage.root / f"{data['id']}.bin").exists()
