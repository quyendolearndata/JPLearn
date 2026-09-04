from __future__ import annotations

import asyncio
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pytest

from helpers import ensure_topics, grant_role, register
from jplearn_api.models import MediaAsset
from jplearn_api.reconciliation import reconcile_orphans
from jplearn_api.storage import InMemoryStorage, LocalFilesystemStorage

VALID_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"payload_bytes"


def _admin(live_client: TestClient) -> str:
    ensure_topics(live_client)
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "admin")
    grant_role(live_client, registered.json()["user"]["id"], "teacher")
    return registered.json()["access_token"]


def _create_item(live_client: TestClient, token: str) -> str:
    response = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "topic_id": "daily_home",
            "ci_level": 0,
            "duration_seconds": 5,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "storage-hardening-test",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ==============================================================================
# 1. G-06 Storage Port Traversal & Parity
# ==============================================================================


def test_storage_path_traversal_guards(tmp_path: Path):
    storage_root = tmp_path / "storage"
    sibling_root = tmp_path / "storage_sibling"
    storage_root.mkdir()
    sibling_root.mkdir()

    storage = LocalFilesystemStorage(storage_root)

    # 1. Parent escape
    with pytest.raises(ValueError, match="Directory traversal detected"):
        storage._resolve("../outside.bin")

    # 2. Sibling directory prefix matching trick
    # e.g. /tmp/.../storage_sibling must not match /tmp/.../storage
    with pytest.raises(ValueError, match="Directory traversal detected"):
        storage._resolve("../storage_sibling/evil.bin")

    # 3. Leading root slash escape
    with pytest.raises(ValueError, match="Directory traversal detected"):
        storage._resolve("/etc/passwd")

    # 4. Nested escape
    with pytest.raises(ValueError, match="Directory traversal detected"):
        storage._resolve("sub/../../escaped.bin")


@pytest.mark.asyncio
async def test_storage_adapter_parity_in_memory_and_filesystem(tmp_path: Path):
    fs_storage = LocalFilesystemStorage(tmp_path / "fs")
    mem_storage = InMemoryStorage()

    for storage in [fs_storage, mem_storage]:
        # Ready probe
        ready_ok, msg = await storage.check_ready()
        assert ready_ok is True
        assert msg == "up"

        # Stage and promote
        async def stream():
            yield b"part1_"
            yield b"part2"

        written = await storage.stage_stream("temp.part", stream())
        assert written == 11

        assert await storage.exists("temp.part") is True
        assert await storage.exists("final.bin") is False

        await storage.promote("temp.part", "final.bin")
        assert await storage.exists("temp.part") is False
        assert await storage.exists("final.bin") is True

        # Metadata
        meta = await storage.get_metadata("final.bin")
        assert meta.size == 11

        # Read
        stream_iter = await storage.open_read("final.bin")
        chunks = [c async for c in stream_iter]
        assert b"".join(chunks) == b"part1_part2"

        # List
        keys = await storage.list_keys()
        assert "final.bin" in keys

        # Delete
        assert await storage.delete("final.bin") is True
        assert await storage.exists("final.bin") is False


# ==============================================================================
# 2. G-07 Media Upload Validation & Magic Bytes
# ==============================================================================


def test_media_upload_extension_and_mime_validation(live_client: TestClient):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin)

    # Invalid extension (.avi)
    bad_ext = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("video.avi", VALID_MP4, "video/mp4")},
    )
    assert bad_ext.status_code == 400
    assert "Invalid file extension" in bad_ext.json()["message"]

    # Invalid MIME (video/quicktime)
    bad_mime = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("video.mp4", VALID_MP4, "video/quicktime")},
    )
    assert bad_mime.status_code == 400
    assert "Invalid MIME type" in bad_mime.json()["message"]


def test_media_upload_magic_bytes_inspection(live_client: TestClient):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin)

    # Empty payload
    empty = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("video.mp4", b"", "video/mp4")},
    )
    assert empty.status_code == 400

    # Shorter than 8 bytes
    too_short = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("video.mp4", b"short", "video/mp4")},
    )
    assert too_short.status_code == 400

    # Corrupted header (missing 'ftyp' at offset 4)
    fake_header = b"\x00\x00\x00\x18corrupt_header_payload"
    corrupt = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("video.mp4", fake_header, "video/mp4")},
    )
    assert corrupt.status_code == 400
    assert "Invalid MP4 file signature" in corrupt.json()["message"]


# ==============================================================================
# 3. G-08 Active Storage Readiness Probe
# ==============================================================================


def test_readiness_probe_active_checks(live_client: TestClient, monkeypatch):
    # Healthy case
    resp = live_client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["database"] == "up"
    assert data["storage"] == "up"

    # Simulated storage probe failure
    storage = live_client.app.state.storage

    async def fail_probe():
        return False, "simulated write failure"

    monkeypatch.setattr(storage, "check_ready", fail_probe)

    down_resp = live_client.get("/ready")
    assert down_resp.status_code == 503
    down_data = down_resp.json()
    assert down_data["ok"] is False
    assert down_data["storage"] == "down"
    assert down_data["database"] == "up"


# ==============================================================================
# 4. G-09 Media Orphan Retention Policy
# ==============================================================================


@pytest.mark.asyncio
async def test_reconciliation_24h_grace_retention(live_client: TestClient):
    from jplearn_api.db import create_engine_and_sessions

    storage = live_client.app.state.storage
    engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)

    try:
        # Create 2 orphan files: one fresh (now), one old (30h ago)
        fresh_key = "fresh_orphan.bin"
        old_key = "old_orphan.bin"

        fresh_path = storage.root / fresh_key
        old_path = storage.root / old_key

        fresh_path.write_bytes(b"fresh")
        old_path.write_bytes(b"old")

        now = time.time()
        # Set old file mtime to 30 hours in past
        old_mtime = now - (30 * 3600)
        import os

        os.utime(old_path, (old_mtime, old_mtime))

        async with sessionmaker() as session:
            # 1. Report-only dry_run
            rep_dry = await reconcile_orphans(session, storage, dry_run=True, now=now)
            assert fresh_key in rep_dry["protected_orphan_keys"]
            assert old_key in rep_dry["eligible_orphan_keys"]
            assert len(rep_dry["deleted_storage_keys"]) == 0
            assert fresh_path.exists()
            assert old_path.exists()

            # 2. Destructive run with confirm_retention_exceeded=True
            rep_run = await reconcile_orphans(
                session,
                storage,
                dry_run=False,
                confirm_retention_exceeded=True,
                now=now,
            )
            # Old orphan deleted
            assert old_key in rep_run["deleted_storage_keys"]
            assert not old_path.exists()

            # Fresh orphan PROTECTED by 24h grace window!
            assert fresh_key not in rep_run["deleted_storage_keys"]
            assert fresh_path.exists()

            # Cleanup fresh file
            fresh_path.unlink(missing_ok=True)
    finally:
        await engine.dispose()
