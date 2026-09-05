from __future__ import annotations

import asyncio
from pathlib import Path
import time
import uuid

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


# ==============================================================================
# 5. R-03: Concurrency & Fault Tolerance for Storage Probe
# ==============================================================================


@pytest.mark.asyncio
async def test_storage_probe_concurrent_100_executions(tmp_path: Path):
    storage = LocalFilesystemStorage(tmp_path / "probe_concurrency_test")
    # Execute 100 concurrent readiness probes
    tasks = [asyncio.create_task(storage.check_ready()) for _ in range(100)]
    results = await asyncio.gather(*tasks)

    for ok, msg in results:
        assert ok is True, f"Probe failed: {msg}"
        assert msg == "up"

    # Verify that NO leftover probe files remain in __probe__/
    probe_dir = storage.root / "__probe__"
    if probe_dir.exists():
        remaining = list(probe_dir.glob("*.tmp"))
        assert len(remaining) == 0, f"Leaked probe files: {remaining}"


@pytest.mark.asyncio
async def test_storage_probe_cleanup_on_failure(tmp_path: Path, monkeypatch):
    storage = LocalFilesystemStorage(tmp_path / "probe_failure_test")

    # Hook into open to simulate readback corruption
    real_open = Path.open

    def faulty_open(path_obj, mode="r", *args, **kwargs):
        handle = real_open(path_obj, mode, *args, **kwargs)
        if "probe_" in path_obj.name and mode == "rb":
            # Return corrupt handle or read wrong bytes
            class CorruptReader:
                def __init__(self, inner):
                    self.inner = inner
                def read(self, *a, **kw):
                    return b"corrupted_probe_content"
                def close(self):
                    self.inner.close()
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    self.close()
            return CorruptReader(handle)
        return handle

    monkeypatch.setattr(Path, "open", faulty_open)

    ok, msg = await storage.check_ready()
    assert ok is False
    assert "Readback mismatch" in msg

    # Even on failure, probe file must be cleaned up via finally
    probe_dir = storage.root / "__probe__"
    if probe_dir.exists():
        remaining = list(probe_dir.glob("*.tmp"))
        assert len(remaining) == 0, f"Leaked probe files after failure: {remaining}"


@pytest.mark.asyncio
async def test_readiness_probe_unlink_permission_error_fails(tmp_path: Path, monkeypatch):
    """R-03: When probe unlink raises PermissionError, check_ready must fail (ok=False)
    and not swallow the error or leak the local filesystem path."""
    storage = LocalFilesystemStorage(tmp_path / "probe_unlink_err")
    real_unlink = Path.unlink

    def faulty_unlink(path_obj, *args, **kwargs):
        if "__probe__" in str(path_obj):
            raise PermissionError("EACCES: permission denied to delete probe file")
        return real_unlink(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", faulty_unlink)

    ok, msg = await storage.check_ready()
    assert ok is False, f"Probe reported healthy ({ok}) despite cleanup failure!"
    assert "PermissionError" in msg or "cleanup failed" in msg.lower()
    # Local path must not be leaked
    assert str(tmp_path) not in msg


@pytest.mark.asyncio
async def test_readiness_bounded_workers_under_timeout_cancel(tmp_path: Path, monkeypatch):
    """R-03: Worker threads cannot exceed max capacity when coroutines timeout/cancel."""
    import threading

    storage = LocalFilesystemStorage(tmp_path / "bounded_workers")
    block_event = threading.Event()
    real_open = Path.open
    active_workers = 0
    max_active_observed = 0
    lock = threading.Lock()

    def blocked_open(path_obj, mode="r", *args, **kwargs):
        nonlocal active_workers, max_active_observed
        if "__probe__" in str(path_obj) and mode == "wb":
            with lock:
                active_workers += 1
                if active_workers > max_active_observed:
                    max_active_observed = active_workers
            block_event.wait(timeout=5)
            with lock:
                active_workers -= 1
        return real_open(path_obj, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", blocked_open)

    try:
        # Launch 3 consecutive batches of 16 requests that timeout after 0.05s
        async def run_with_timeout():
            try:
                await asyncio.wait_for(storage.check_ready(), timeout=0.05)
            except (TimeoutError, asyncio.TimeoutError):
                pass

        for _ in range(3):
            tasks = [asyncio.create_task(run_with_timeout()) for _ in range(16)]
            await asyncio.gather(*tasks)

        # Workers running concurrently in background must NOT exceed bounded capacity (16)
        with lock:
            assert max_active_observed <= 16, f"Worker explosion: {max_active_observed} workers exceeded limit 16!"
    finally:
        block_event.set()
        # Allow background workers to drain
        await asyncio.sleep(0.1)


def test_readiness_probe_db_timeout_liveness_intact(live_client: TestClient, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    # Liveness remains intact
    health_resp = live_client.get("/health")
    assert health_resp.status_code == 200

    # Simulate slow/hanging DB query
    async def slow_execute(self, *args, **kwargs):
        await asyncio.sleep(3.0)

    monkeypatch.setattr(AsyncSession, "execute", slow_execute)

    ready_resp = live_client.get("/ready")
    assert ready_resp.status_code == 503
    ready_data = ready_resp.json()
    assert ready_data["ok"] is False
    assert ready_data["database"] == "down"


def test_readiness_probe_storage_timeout_db_intact(live_client: TestClient, monkeypatch):
    """R-03: Storage probe timeout must report storage: 'down' while keeping database: 'up'."""
    storage = live_client.app.state.storage

    async def slow_check_ready():
        await asyncio.sleep(3.0)
        return True, "up"

    monkeypatch.setattr(storage, "check_ready", slow_check_ready)

    ready_resp = live_client.get("/ready")
    assert ready_resp.status_code == 503
    ready_data = ready_resp.json()
    assert ready_data["ok"] is False
    assert ready_data["database"] == "up"
    assert ready_data["storage"] == "down"


# ==============================================================================
# 6. R-05: Hardened Orphan Retention, Boundary & Race Conditions
# ==============================================================================


@pytest.mark.asyncio
async def test_reconciliation_retention_policy_validation(live_client: TestClient):
    from jplearn_api.db import create_engine_and_sessions

    storage = live_client.app.state.storage
    engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)

    try:
        async with sessionmaker() as session:
            # Rejects retention less than 24h
            with pytest.raises(ValueError, match="retention_seconds must be a finite number >= 86400"):
                await reconcile_orphans(session, storage, retention_seconds=3600)

            # Rejects negative retention
            with pytest.raises(ValueError, match="retention_seconds must be a finite number >= 86400"):
                await reconcile_orphans(session, storage, retention_seconds=-100)

            # Rejects NaN
            with pytest.raises(ValueError, match="retention_seconds must be a finite number >= 86400"):
                await reconcile_orphans(session, storage, retention_seconds=float("nan"))
    finally:
        await engine.dispose()


def test_reconciliation_metadata_protection_and_race_prevention(live_client: TestClient):
    import os
    from jplearn_api.db import create_engine_and_sessions

    admin = _admin(live_client)
    item_id = _create_item(live_client, admin)

    storage = live_client.app.state.storage

    async def _run():
        engine, sessionmaker = create_engine_and_sessions(live_client.app.state.settings)
        try:
            now = time.time()
            # 1. Exactly at boundary: 24h - 1s (protected), 24h + 1s (eligible)
            boundary_young = "boundary_young.bin"
            boundary_old = "boundary_old.bin"
            future_file = "future_file.bin"
            part_file = "uploading.part"

            (storage.root / boundary_young).write_bytes(b"young")
            (storage.root / boundary_old).write_bytes(b"old")
            (storage.root / future_file).write_bytes(b"future")
            (storage.root / part_file).write_bytes(b"in_flight")

            os.utime(storage.root / boundary_young, (now - 86390, now - 86390))
            os.utime(storage.root / boundary_old, (now - 86410, now - 86410))
            os.utime(storage.root / future_file, (now + 7200, now + 7200))

            async with sessionmaker() as session:
                rep = await reconcile_orphans(session, storage, dry_run=True, now=now)

                # Part file must never be in orphan list
                assert part_file not in rep["orphan_storage_keys"]

                # Young boundary file protected
                assert boundary_young in rep["protected_orphan_keys"]
                assert boundary_young not in rep["eligible_orphan_keys"]

                # Future file protected and recorded in unknown_metadata_keys
                assert future_file in rep["protected_orphan_keys"]
                assert future_file in rep["unknown_metadata_keys"]
                assert future_file not in rep["eligible_orphan_keys"]

                # Old boundary file eligible
                assert boundary_old in rep["eligible_orphan_keys"]

                # 2. Race prevention test:
                # If an eligible orphan is inserted into the DB right before deletion,
                # reconcile_orphans must re-check and refuse to delete it!
                racing_key = boundary_old
                racing_asset = MediaAsset(
                    id=str(uuid.uuid4()),
                    catalog_item_id=item_id,
                    storage_key=racing_key,
                    mime="video/mp4",
                )
                session.add(racing_asset)
                await session.commit()

                # Now execute deletion
                rep_race = await reconcile_orphans(
                    session,
                    storage,
                    dry_run=False,
                    confirm_retention_exceeded=True,
                    now=now,
                )

                # racing_key should NOT be deleted because pre-delete recheck caught it
                assert racing_key not in rep_race["deleted_storage_keys"]
                assert (storage.root / racing_key).exists()

                # Clean up test DB row
                await session.delete(racing_asset)
                await session.commit()
        finally:
            (storage.root / boundary_young).unlink(missing_ok=True)
            (storage.root / boundary_old).unlink(missing_ok=True)
            (storage.root / future_file).unlink(missing_ok=True)
            (storage.root / part_file).unlink(missing_ok=True)
            await engine.dispose()

    asyncio.run(_run())


def test_reconciliation_cli_args_parsing():
    from jplearn_api.reconciliation import parse_args

    # Default is dry_run = True, retention_hours = 24.0
    args = parse_args([])
    assert args.dry_run is True
    assert args.confirm_retention_exceeded is False
    assert args.retention_hours == 24.0

    # Explicit execute / delete flags
    args2 = parse_args(["--execute", "--confirm-retention-exceeded", "--retention-hours", "48.0"])
    assert args2.dry_run is False
    assert args2.confirm_retention_exceeded is True
    assert args2.retention_hours == 48.0

    # Reject retention below 24h
    with pytest.raises(SystemExit):
        parse_args(["--retention-hours", "12.0"])

    # Reject --force-delete
    with pytest.raises(SystemExit):
        parse_args(["--force-delete"])


# ==============================================================================
# 7. R-07/A: Storage I/O Cancellation & Ownership
# ==============================================================================


@pytest.mark.asyncio
async def test_stage_stream_cancellation_during_late_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """R-07/A: When cancelled while executor is opening the file, the returned
    file handle must be safely closed and .part unlinked by the completing thread."""
    import threading

    storage = LocalFilesystemStorage(tmp_path / "late_open_test")
    temp_key = "late_open.part"
    temp_path = storage.root / temp_key

    open_started = threading.Event()
    allow_open_finish = threading.Event()
    captured_handles = []
    real_open = Path.open

    def delayed_open(self_path, mode="r", *args, **kwargs):
        handle = real_open(self_path, mode, *args, **kwargs)
        if "late_open.part" in str(self_path):
            captured_handles.append(handle)
            open_started.set()
            allow_open_finish.wait(timeout=5.0)
        return handle

    monkeypatch.setattr(Path, "open", delayed_open)

    async def dummy_stream():
        yield b"never_sent"

    task = asyncio.create_task(storage.stage_stream(temp_key, dummy_stream()))

    while not open_started.is_set():
        await asyncio.sleep(0.01)

    # Cancel the asyncio task while open() is blocked in worker thread
    task.cancel()

    # Allow delayed_open to finish
    allow_open_finish.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    # Assert captured handle was closed
    assert len(captured_handles) == 1
    assert captured_handles[0].closed is True, "File handle was leaked open after cancellation!"

    # Assert .part file was unlinked and does not exist on disk
    assert not temp_path.exists(), f"Orphaned .part file remained on disk: {temp_path}"


@pytest.mark.asyncio
async def test_stage_stream_cancellation_during_in_flight_write(tmp_path: Path):
    """R-07/A: When cancelled while executor write is in-flight, cleanup must wait
    for the active write to complete before closing handle and unlinking."""
    import threading

    storage = LocalFilesystemStorage(tmp_path / "write_cancel_test")
    temp_key = "write_cancel.part"
    temp_path = storage.root / temp_key

    write_started = threading.Event()
    allow_write_finish = threading.Event()

    from jplearn_api.storage import _StagingSession

    real_sync_write = _StagingSession.sync_write
    written_successfully = []

    def delayed_sync_write(self_session, chunk: bytes) -> int:
        write_started.set()
        allow_write_finish.wait(timeout=5.0)
        res = real_sync_write(self_session, chunk)
        written_successfully.append(res)
        return res

    _StagingSession.sync_write = delayed_sync_write  # type: ignore[assignment]

    try:
        async def slow_stream():
            yield b"payload_chunk_data"

        task = asyncio.create_task(storage.stage_stream(temp_key, slow_stream()))

        while not write_started.is_set():
            await asyncio.sleep(0.01)

        # Cancel the task while write is in-flight
        task.cancel()

        # Allow delayed write to finish
        allow_write_finish.set()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert len(written_successfully) == 1
        assert not temp_path.exists(), "Part file was not unlinked after cancellation!"
    finally:
        _StagingSession.sync_write = real_sync_write  # type: ignore[assignment]


def test_staging_cleanup_defers_close_and_unlink_after_drain_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-07/A: timeout transfers cleanup ownership to the active I/O worker."""
    import threading

    from jplearn_api import storage as storage_mod

    temp_path = tmp_path / "deferred.part"
    temp_path.touch()
    write_started = threading.Event()
    allow_write_finish = threading.Event()

    class BarrierHandle:
        closed = False
        close_while_write_active = False

        def write(self, chunk: bytes) -> int:
            write_started.set()
            allow_write_finish.wait(timeout=2.0)
            return len(chunk)

        def close(self) -> None:
            self.close_while_write_active = not allow_write_finish.is_set()
            self.closed = True

    monkeypatch.setattr(storage_mod, "STAGING_DRAIN_TIMEOUT_SECONDS", 0.01)
    session = storage_mod._StagingSession(temp_path)
    handle = BarrierHandle()
    session.file_handle = handle

    writer = threading.Thread(target=session.sync_write, args=(b"payload",))
    writer.start()
    assert write_started.wait(timeout=1.0)

    session.sync_cleanup(remove_file=True)

    assert handle.closed is False
    assert temp_path.exists()

    allow_write_finish.set()
    writer.join(timeout=1.0)

    assert not writer.is_alive()
    assert handle.closed is True
    assert handle.close_while_write_active is False
    assert not temp_path.exists()


@pytest.mark.asyncio
async def test_stage_stream_cleanup_failure_logging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """R-07/A: When cleanup unlink raises an error, it must be logged with structured error."""
    storage = LocalFilesystemStorage(tmp_path / "cleanup_err_test")
    temp_key = "cleanup_err.part"

    real_unlink = Path.unlink

    def faulty_unlink(self_path, *args, **kwargs):
        if "cleanup_err.part" in str(self_path):
            raise PermissionError("Permission denied during test cleanup")
        return real_unlink(self_path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", faulty_unlink)

    logged_errors = []
    from jplearn_api import storage as storage_mod

    real_error = storage_mod.logger.error

    def capture_error(msg, *args, **kwargs):
        logged_errors.append((msg, kwargs.get("extra", {})))
        return real_error(msg, *args, **kwargs)

    monkeypatch.setattr(storage_mod.logger, "error", capture_error)

    async def invalid_stream():
        if False:
            yield b""

    with pytest.raises(ValueError, match="File must not be empty"):
        await storage.stage_stream(temp_key, invalid_stream())

    # Verify structured failure log
    cleanup_logs = [e for e in logged_errors if e[0] == "storage_staging_cleanup_failed"]
    assert len(cleanup_logs) == 1
    assert cleanup_logs[0][1].get("unlink_error") == "PermissionError"

