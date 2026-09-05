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

