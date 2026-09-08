"""Unit, handler, and contract tests for Playback Tracking, Leases, and Checkpoints (PR4 / UC-L16 / UC-L17 / FR-WAT-001 / FR-RSM-001)."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    EndPlaybackCommand,
    SendCheckpointCommand,
    StartPlaybackCommand,
)
from jplearn_api.application.handlers.playback import (
    handle_end_playback,
    handle_get_item_resume,
    handle_get_playback,
    handle_list_resume,
    handle_send_checkpoint,
    handle_start_playback,
    split_delta_by_timezone,
)
from jplearn_api.application.queries import (
    GetItemResumeQuery,
    GetPlaybackQuery,
    ListResumeQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.content import ContentVersion
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.domain.playback import (
    PlaybackCheckpoint,
    PlaybackReceipt,
    PlaybackSession,
    PlaybackStatus,
    PlayerState,
)
from jplearn_api.entrypoints.http.security import require_user
from fakes import (
    FakeCatalogRepository,
    FakeContentRepository,
    FakePlaybackRepository,
    FakeUnitOfWork,
)


@pytest.fixture
def test_env():
    catalog_repo = FakeCatalogRepository()
    content_repo = FakeContentRepository()
    playback_repo = FakePlaybackRepository()

    # Published catalog item with published version
    item = CatalogItem(
        id="item-01",
        topic_id="daily-life",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="high",
        title_internal="Lesson 1",
        created_by="teacher-01",
        status="published",
    )
    catalog_repo._committed_items[item.id] = item
    catalog_repo.items[item.id] = item

    ver = ContentVersion(
        id="ver-pub-01",
        catalog_item_id="item-01",
        version_number=1,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=[],
    )
    content_repo._committed_versions.setdefault(item.id, []).append(ver)
    content_repo.versions = copy.deepcopy(content_repo._committed_versions)

    # Unpublished draft catalog item
    draft_item = CatalogItem(
        id="item-draft",
        topic_id="daily-life",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="high",
        title_internal="Draft Lesson",
        created_by="teacher-01",
        status="draft",
    )
    catalog_repo._committed_items[draft_item.id] = draft_item
    catalog_repo.items[draft_item.id] = draft_item

    uow = FakeUnitOfWork(
        catalog=catalog_repo,
        content=content_repo,
        playbacks=playback_repo,
    )
    return {
        "uow": uow,
        "catalog": catalog_repo,
        "playbacks": playback_repo,
    }



# ------------------------------------------------------------------------------
# 1. Midnight Split & Timezone Calculation Tests
# ------------------------------------------------------------------------------

def test_split_delta_same_day():
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    start = datetime(2026, 9, 7, 10, 0, 0, tzinfo=tz)
    end = datetime(2026, 9, 7, 10, 0, 15, tzinfo=tz)
    delta_ms = 15000

    alloc = split_delta_by_timezone(start, end, delta_ms, "Asia/Ho_Chi_Minh")
    assert len(alloc) == 1
    assert alloc[0] == ("2026-09-07", 15000)


def test_split_delta_midnight_transition():
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    # 23:59:50 to 00:00:10 (20s total: 10s on Sep 7, 10s on Sep 8)
    start = datetime(2026, 9, 7, 23, 59, 50, tzinfo=tz)
    end = datetime(2026, 9, 8, 0, 0, 10, tzinfo=tz)
    delta_ms = 20000

    alloc = split_delta_by_timezone(start, end, delta_ms, "Asia/Ho_Chi_Minh")
    assert len(alloc) == 2
    assert alloc[0] == ("2026-09-07", 10000)
    assert alloc[1] == ("2026-09-08", 10000)
    assert sum(ms for _, ms in alloc) == delta_ms


def test_split_delta_zero_or_negative():
    now = datetime.now(timezone.utc)
    alloc = split_delta_by_timezone(now, now, 0, "Asia/Ho_Chi_Minh")
    assert len(alloc) == 1
    assert alloc[0][1] == 0


# ------------------------------------------------------------------------------
# 2. Application Handlers: Start Playback & Lease Management
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_playback_success(test_env):
    uow = test_env["uow"]
    cmd = StartPlaybackCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        device_id="dev-web-01",
    )
    session, resume_cp = await handle_start_playback(cmd, uow)
    assert session.id is not None
    assert session.user_id == "user-01"
    assert session.catalog_item_id == "item-01"
    assert session.content_version_id == "ver-pub-01"
    assert session.status == PlaybackStatus.ACTIVE
    assert session.epoch == 1
    assert resume_cp is None


@pytest.mark.asyncio
async def test_start_playback_unpublished_or_not_found(test_env):
    uow = test_env["uow"]
    with pytest.raises(EntityNotFoundError, match="Catalog item not found"):
        await handle_start_playback(
            StartPlaybackCommand(user_id="user-01", catalog_item_id="non-existent", device_id="dev-01"),
            uow,
        )

    with pytest.raises(InvalidDomainStateError, match="Cannot play an unpublished catalog item"):
        await handle_start_playback(
            StartPlaybackCommand(user_id="user-01", catalog_item_id="item-draft", device_id="dev-01"),
            uow,
        )


@pytest.mark.asyncio
async def test_single_active_lease_conflict_and_takeover(test_env):
    uow = test_env["uow"]

    # 1. Device A starts playback
    cmd_a = StartPlaybackCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        device_id="dev-phone",
    )
    session_a, _ = await handle_start_playback(cmd_a, uow)
    assert session_a.epoch == 1

    # 2. Device B attempts to start without take_over -> 409 Conflict
    cmd_b_no_takeover = StartPlaybackCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        device_id="dev-laptop",
        take_over=False,
    )
    with pytest.raises(ConflictError, match="Another playback session is currently active"):
        await handle_start_playback(cmd_b_no_takeover, uow)

    # 3. Device B starts with take_over=True -> Succeeds and bumps epoch to 2
    cmd_b_takeover = StartPlaybackCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        device_id="dev-laptop",
        take_over=True,
    )
    session_b, _ = await handle_start_playback(cmd_b_takeover, uow)
    assert session_b.epoch == 2

    # 4. Old session A should be superseded
    old_a = await uow.playbacks.get_playback(session_a.id)
    assert old_a.status == PlaybackStatus.SUPERSEDED

    # 5. Device A attempts to send checkpoint -> ConflictError (superseded)
    cmd_a_cp = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session_a.id,
        seq=1,
        position_ms=15000,
        duration_ms=60000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=15000,
        client_epoch=1,
    )
    with pytest.raises(ConflictError, match="superseded"):
        await handle_send_checkpoint(cmd_a_cp, uow)


# ------------------------------------------------------------------------------
# 3. Application Handlers: Checkpoint Accounting & Anti-Cheat
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heartbeat_accounting_and_rate_limit(test_env):
    uow = test_env["uow"]

    session, _ = await handle_start_playback(
        StartPlaybackCommand(user_id="user-01", catalog_item_id="item-01", device_id="dev-01"),
        uow,
    )

    # Checkpoint 1 (seq=1, normal play for 15s)
    cmd_1 = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=1,
        position_ms=15000,
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=15000,
        client_epoch=session.epoch,
    )
    receipt_1, updated_session = await handle_send_checkpoint(cmd_1, uow)
    assert receipt_1.seq == 1
    assert receipt_1.accepted_delta_ms <= 17000  # Within tolerance
    assert updated_session.total_active_ms == receipt_1.cumulative_active_ms

    # Checkpoint 2 (seq=2, seek forward: position jumps 15s -> 90s, but active time only increments 15s)
    cmd_2 = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=2,
        position_ms=90000,  # Giant seek
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=30000,  # Client only claims +15000ms active
        client_epoch=session.epoch,
    )
    receipt_2, updated_session = await handle_send_checkpoint(cmd_2, uow)
    assert receipt_2.seq == 2
    assert receipt_2.accepted_delta_ms <= 17000  # Does NOT credit 75s seek
    assert updated_session.last_position_ms == 90000


@pytest.mark.asyncio
async def test_heartbeat_gap_threshold_resets_credit(test_env):
    uow = test_env["uow"]

    session, _ = await handle_start_playback(
        StartPlaybackCommand(user_id="user-01", catalog_item_id="item-01", device_id="dev-01"),
        uow,
    )

    # 1. Normal checkpoint 1
    cmd_1 = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=1,
        position_ms=15000,
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=15000,
        client_epoch=session.epoch,
    )
    receipt_1, s1 = await handle_send_checkpoint(cmd_1, uow)
    initial_acknowledged = s1.total_active_ms

    # 2. Fast forward session's last_server_time to simulate 60s gap (> 30s threshold)
    test_env["playbacks"]._committed_playbacks[session.id].last_server_time = datetime.now(timezone.utc) - timedelta(seconds=60)
    test_env["playbacks"].playbacks[session.id].last_server_time = datetime.now(timezone.utc) - timedelta(seconds=60)

    # 3. Next checkpoint seq=2 arrives after 60s
    cmd_gap = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=2,
        position_ms=75000,
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=75000,
        client_epoch=session.epoch,
    )
    receipt_gap, updated_session = await handle_send_checkpoint(cmd_gap, uow)
    assert receipt_gap.accepted_delta_ms == 0  # Zero credit due to >30s gap!
    assert updated_session.total_active_ms == initial_acknowledged  # Total active did not increase



@pytest.mark.asyncio
async def test_checkpoint_sequence_and_idempotency_replay(test_env):
    uow = test_env["uow"]

    session, _ = await handle_start_playback(
        StartPlaybackCommand(user_id="user-01", catalog_item_id="item-01", device_id="dev-01"),
        uow,
    )

    # 1. Checkpoint 1
    cmd_1 = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=1,
        position_ms=15000,
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=15000,
        client_epoch=session.epoch,
    )
    receipt_1, _ = await handle_send_checkpoint(cmd_1, uow)

    # 2. Replay Checkpoint 1 with same payload -> idempotent receipt returned
    receipt_1_replay, _ = await handle_send_checkpoint(cmd_1, uow)
    assert receipt_1_replay.seq == 1
    assert receipt_1_replay.request_hash == receipt_1.request_hash

    # 3. Retry Checkpoint 1 with different payload -> 409 Conflict
    cmd_1_conflict = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=1,
        position_ms=99999,  # Conflicting position
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=15000,
        client_epoch=session.epoch,
    )
    with pytest.raises(ConflictError, match="Duplicate sequence 1 with conflicting payload"):
        await handle_send_checkpoint(cmd_1_conflict, uow)

    # 4. Sequence gap (seq=1 to seq=3) -> 409 Conflict
    cmd_3 = SendCheckpointCommand(
        user_id="user-01",
        playback_id=session.id,
        seq=3,  # Skipped 2
        position_ms=30000,
        duration_ms=120000,
        playback_rate=1.0,
        state=PlayerState.PLAYING.value,
        client_cumulative_active_ms=30000,
        client_epoch=session.epoch,
    )
    with pytest.raises(ConflictError, match="Sequence gap: expected 2, received 3"):
        await handle_send_checkpoint(cmd_3, uow)


# ------------------------------------------------------------------------------
# 4. HTTP API Contract & Integration Tests
# ------------------------------------------------------------------------------

def test_api_playback_full_lifecycle(client: TestClient, monkeypatch: pytest.MonkeyPatch, test_env):
    uow = test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.playbacks.create_uow", lambda session: uow)

    from jplearn_api.entrypoints.http.dependencies import require_capability

    auth_user = UserDTO(id="user-01", email="learner@example.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: auth_user
    client.app.dependency_overrides[require_capability("playback_tracking_enabled")] = lambda: None

    # 1. Start playback on Device 1
    res_start = client.post(
        "/playbacks",
        json={
            "catalog_item_id": "item-01",
            "device_id": "web-chrome-01",
        },
    )
    assert res_start.status_code == 201
    data_start = res_start.json()
    playback_id = data_start["playback_id"]
    assert data_start["epoch"] == 1
    assert data_start["initial_position_ms"] == 0

    # 2. Get playback status
    res_get = client.get(f"/playbacks/{playback_id}")
    assert res_get.status_code == 200
    assert res_get.json()["status"] == "active"

    # 3. Send checkpoint 1
    res_cp1 = client.put(
        f"/playbacks/{playback_id}/checkpoints/1",
        json={
            "position_ms": 15000,
            "duration_ms": 100000,
            "playback_rate": 1.0,
            "state": "playing",
            "client_cumulative_active_ms": 15000,
            "client_epoch": 1,
        },
    )
    assert res_cp1.status_code == 200
    assert res_cp1.json()["seq"] == 1

    # 4. Device 2 starts playback with take_over=True
    res_takeover = client.post(
        "/playbacks",
        json={
            "catalog_item_id": "item-01",
            "device_id": "mobile-app-02",
            "take_over": True,
        },
    )
    assert res_takeover.status_code == 201
    data_takeover = res_takeover.json()
    assert data_takeover["epoch"] == 2
    assert data_takeover["initial_position_ms"] == 15000  # Resumed from checkpoint!
    assert data_takeover["resume_checkpoint"]["position_ms"] == 15000

    # 5. Check resume list
    res_resume = client.get("/me/resume")
    assert res_resume.status_code == 200
    items = res_resume.json()["items"]
    assert len(items) == 1
    assert items[0]["catalog_item_id"] == "item-01"
    assert items[0]["position_ms"] == 15000

    # 6. Check single item resume
    res_single_resume = client.get("/me/resume/item-01")
    assert res_single_resume.status_code == 200
    assert res_single_resume.json()["position_ms"] == 15000

    # 7. Device 1 attempts next checkpoint on old session -> 409 Conflict
    res_old_cp = client.put(
        f"/playbacks/{playback_id}/checkpoints/2",
        json={
            "position_ms": 30000,
            "duration_ms": 100000,
            "playback_rate": 1.0,
            "state": "playing",
            "client_cumulative_active_ms": 30000,
            "client_epoch": 1,
        },
    )
    assert res_old_cp.status_code == 409

    # 8. End session on Device 2
    new_playback_id = data_takeover["playback_id"]
    res_end = client.post(f"/playbacks/{new_playback_id}/end", json={"final_seq": 1, "final_position_ms": 20000})
    assert res_end.status_code == 200
    assert res_end.json()["status"] == "completed"


# ------------------------------------------------------------------------------
# R3 & R4 Remediation Tests (P1.3, P1.4, P1.6, P1.7)
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_lease_epoch_bump_and_fencing(test_env):
    """R3 (P1.3): When lease expires and a new writer starts, epoch is bumped and old writer is fenced."""
    uow = test_env["uow"]

    # 1. Device A starts playback
    s1, _ = await handle_start_playback(
        StartPlaybackCommand("user-01", "item-01", "device-A", {}),
        uow,
    )
    assert s1.epoch == 1

    # 2. Simulate lease expiration: expire lease timestamp in learner_playback_state
    async with uow:
        state = await uow.playbacks.acquire_learner_playback_lock("user-01", "web", "device-A")
        state.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        await uow.playbacks.update_learner_playback_state(state)
        await uow.commit()

    # 3. Device B starts playback without takeover flag (allowed because lease expired)
    s2, _ = await handle_start_playback(
        StartPlaybackCommand("user-01", "item-01", "device-B", {}),
        uow,
    )
    assert s2.epoch == 2
    assert s2.id != s1.id

    # Verify old session was superseded in DB
    old_s = await uow.playbacks.get_playback(s1.id)
    assert old_s.status == PlaybackStatus.SUPERSEDED

    # 4. Device A wakes up and sends checkpoint with epoch 1 -> 409 Conflict
    with pytest.raises(ConflictError, match="superseded"):
        await handle_send_checkpoint(
            SendCheckpointCommand(
                playback_id=s1.id,
                user_id="user-01",
                seq=1,
                position_ms=15000,
                duration_ms=60000,
                playback_rate=1.0,
                state="playing",
                client_cumulative_active_ms=15000,
                client_epoch=1,
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_idempotent_receipt_replay_on_superseded_session(test_env):
    """R3 (P1.7): Idempotent checkpoint retry must return receipt even after session was superseded."""
    uow = test_env["uow"]

    # 1. Device A starts playback & sends checkpoint 1
    s1, _ = await handle_start_playback(
        StartPlaybackCommand("user-01", "item-01", "device-A", {}),
        uow,
    )
    cp_cmd = SendCheckpointCommand(
        playback_id=s1.id,
        user_id="user-01",
        seq=1,
        position_ms=10000,
        duration_ms=60000,
        playback_rate=1.0,
        state="playing",
        client_cumulative_active_ms=10000,
        client_epoch=1,
    )
    receipt1, _ = await handle_send_checkpoint(cp_cmd, uow)
    assert receipt1.seq == 1

    # 2. Device B takes over -> session 1 is superseded
    await handle_start_playback(
        StartPlaybackCommand("user-01", "item-01", "device-B", {}, take_over=True),
        uow,
    )
    old_s = await uow.playbacks.get_playback(s1.id)
    assert old_s.status == PlaybackStatus.SUPERSEDED

    # 3. Device A retries checkpoint 1 (e.g. network dropped the ACK previously)
    # Must succeed by replaying stored receipt rather than throwing 409 Conflict!
    retry_receipt, _ = await handle_send_checkpoint(cp_cmd, uow)
    assert retry_receipt.seq == 1
    assert retry_receipt.request_hash == receipt1.request_hash


@pytest.mark.asyncio
async def test_wall_clock_active_time_no_multiplier(test_env):
    """R4 (P1.6): Active immersion time is capped by wall clock elapsed, without multiplying by playback rate."""
    uow = test_env["uow"]

    s, _ = await handle_start_playback(
        StartPlaybackCommand("user-01", "item-01", "device-A", {}),
        uow,
    )

    # Set last_server_time to exactly 15 seconds ago and commit
    async with uow:
        s_db = await uow.playbacks.get_playback(s.id)
        now = datetime.now(timezone.utc)
        s_db.last_server_time = now - timedelta(seconds=15)
        s_db.created_at = s_db.last_server_time
        await uow.playbacks.update_playback(s_db)
        await uow.commit()

    # Client played at 2.0x speed and claims 30 seconds of content active time
    receipt, updated_session = await handle_send_checkpoint(
        SendCheckpointCommand(
            playback_id=s.id,
            user_id="user-01",
            seq=1,
            position_ms=30000,
            duration_ms=100000,
            playback_rate=2.0,
            state="playing",
            client_cumulative_active_ms=30000,
            client_epoch=1,
        ),
        uow,
    )

    # Server elapsed was 15s (+ tolerance), so accepted active time must NOT be 30s!
    # Max allowed = 15000 + 2000 (tolerance) = 17000ms
    assert receipt.accepted_delta_ms <= 17000
    assert receipt.accepted_delta_ms >= 15000
    assert updated_session.total_active_ms == receipt.accepted_delta_ms


@pytest.mark.asyncio
async def test_late_end_checkpoint_fenced_by_deletion(test_env):
    """R3 (P1.4): If watch history was deleted, late end checkpoint must not resurrect resume checkpoint."""
    from jplearn_api.application.commands import RequestHistoryDeletionCommand
    from jplearn_api.application.handlers.activity import handle_request_history_deletion

    uow = test_env["uow"]

    # 1. Start playback
    s, _ = await handle_start_playback(
        StartPlaybackCommand("user-01", "item-01", "device-A", {}),
        uow,
    )

    # 2. Learner requests history deletion
    await handle_request_history_deletion(
        RequestHistoryDeletionCommand(user_id="user-01"),
        uow,
    )

    # 3. Old session attempts to end and save resume position
    end_cmd = EndPlaybackCommand(
        playback_id=s.id,
        user_id="user-01",
        final_seq=1,
        final_position_ms=45000,
        final_duration_ms=100000,
        final_playback_rate=1.0,
        final_client_cumulative_active_ms=45000,
        final_client_epoch=1,
    )
    await handle_end_playback(end_cmd, uow)

    # Verify that resume checkpoint was NOT saved
    cp = await uow.playbacks.get_checkpoint("user-01", "item-01")
    assert cp is None
