"""Unit, handler, and contract tests for Learning Preferences, Daily Activity, Watch History, and History Deletions.

Validates:
- UC-L16: Goal setting (0-120 mins), preferred topics, IANA timezone, OCC revisioning.
- Next local midnight (00:00:00) effective boundary without retroactive changes.
- Daily Activity max 90-day range query and metric integrity (active_watch_seconds).
- FR-NEG: No grammar/CI/flashcard metrics.
- FR-WAT-001: Watch history cursor pagination and isolation before cutoff time.
- Deletion: 202 Accepted, immediate session closure & lease revocation, async worker purge.
- Non-destructive retention of daily activity, saved scenes, and personal collections.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from fakes import (
    FakeCollectionRepository,
    FakePlaybackRepository,
    FakeSavedSceneRepository,
    FakeUnitOfWork,
)
from jplearn_api.application.commands import (
    RequestHistoryDeletionCommand,
    UpdateLearningPreferencesCommand,
)
from jplearn_api.application.handlers.activity import (
    calculate_activity_streaks,
    handle_execute_history_deletion_worker,
    handle_get_daily_activity,
    handle_get_learning_preferences,
    handle_get_watch_history,
    handle_request_history_deletion,
    handle_update_learning_preferences,
)
from jplearn_api.application.queries import (
    GetDailyActivityQuery,
    GetLearningPreferencesQuery,
    GetWatchHistoryQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.collection import PersonalCollection
from jplearn_api.domain.errors import (
    InvalidDomainStateError,
    RevisionConflictError,
)
from jplearn_api.domain.playback import (
    DeletionStatus,
    LearnerDailyActivity,
    PlaybackCheckpoint,
    PlaybackSession,
    PlaybackStatus,
)
from jplearn_api.domain.saved_scene import SavedScene
from jplearn_api.entrypoints.http.security import require_user


@pytest.fixture
def activity_env():
    playback_repo = FakePlaybackRepository()
    saved_scenes_repo = FakeSavedSceneRepository()
    collection_repo = FakeCollectionRepository()

    uow = FakeUnitOfWork(
        playbacks=playback_repo,
        saved_scenes=saved_scenes_repo,
        collections=collection_repo,
    )
    return {
        "uow": uow,
        "playbacks": playback_repo,
        "saved_scenes": saved_scenes_repo,
        "collections": collection_repo,
    }


# ------------------------------------------------------------------------------
# 1. Learning Preferences Handlers & OCC Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_default_preferences(activity_env):
    uow = activity_env["uow"]
    query = GetLearningPreferencesQuery(user_id="user-01")
    pref = await handle_get_learning_preferences(query, uow)

    assert pref.user_id == "user-01"
    assert pref.daily_goal_minutes == 15
    assert pref.preferred_topic_ids == []
    assert pref.timezone == "Asia/Ho_Chi_Minh"
    assert pref.revision == 1


@pytest.mark.asyncio
async def test_update_learning_preferences_success_and_effective_at_boundary(activity_env):
    uow = activity_env["uow"]
    cmd = UpdateLearningPreferencesCommand(
        user_id="user-01",
        expected_revision=1,
        daily_goal_minutes=45,
        preferred_topic_ids=["topic-food", "topic-travel"],
        timezone="Asia/Tokyo",
    )
    pref = await handle_update_learning_preferences(cmd, uow)

    assert pref.daily_goal_minutes == 45
    assert pref.preferred_topic_ids == ["topic-food", "topic-travel"]
    assert pref.timezone == "Asia/Tokyo"
    assert pref.revision == 2

    # effective_at must be midnight of next day in previous learner timezone ("Asia/Ho_Chi_Minh")
    hcm_tz = ZoneInfo("Asia/Ho_Chi_Minh")
    now_hcm = datetime.now(UTC).astimezone(hcm_tz)
    next_day_hcm = now_hcm.date() + timedelta(days=1)
    expected_midnight = datetime(next_day_hcm.year, next_day_hcm.month, next_day_hcm.day, 0, 0, 0, tzinfo=hcm_tz)
    assert pref.effective_at == expected_midnight.astimezone(UTC)


@pytest.mark.asyncio
async def test_update_learning_preferences_occ_conflict(activity_env):
    uow = activity_env["uow"]
    cmd = UpdateLearningPreferencesCommand(
        user_id="user-01",
        expected_revision=999,  # Mismatch (current is 1)
        daily_goal_minutes=30,
    )
    with pytest.raises(RevisionConflictError, match="Revision conflict: expected 999, got 1"):
        await handle_update_learning_preferences(cmd, uow)


@pytest.mark.asyncio
async def test_update_learning_preferences_goal_boundaries(activity_env):
    uow = activity_env["uow"]

    # 0 is valid (disabled)
    cmd_zero = UpdateLearningPreferencesCommand(user_id="user-01", expected_revision=1, daily_goal_minutes=0)
    p0 = await handle_update_learning_preferences(cmd_zero, uow)
    assert p0.daily_goal_minutes == 0

    # 120 is valid (maximum)
    cmd_max = UpdateLearningPreferencesCommand(user_id="user-01", expected_revision=2, daily_goal_minutes=120)
    p120 = await handle_update_learning_preferences(cmd_max, uow)
    assert p120.daily_goal_minutes == 120

    # > 120 is invalid
    cmd_over = UpdateLearningPreferencesCommand(user_id="user-01", expected_revision=3, daily_goal_minutes=121)
    with pytest.raises(InvalidDomainStateError, match="daily_goal_minutes must be between 0 and 120"):
        await handle_update_learning_preferences(cmd_over, uow)

    # < 0 is invalid
    cmd_neg = UpdateLearningPreferencesCommand(user_id="user-01", expected_revision=3, daily_goal_minutes=-1)
    with pytest.raises(InvalidDomainStateError, match="daily_goal_minutes must be between 0 and 120"):
        await handle_update_learning_preferences(cmd_neg, uow)


@pytest.mark.asyncio
async def test_update_learning_preferences_invalid_timezone(activity_env):
    uow = activity_env["uow"]
    cmd = UpdateLearningPreferencesCommand(
        user_id="user-01",
        expected_revision=1,
        timezone="Moon/Crater",
    )
    with pytest.raises(InvalidDomainStateError, match="Invalid IANA timezone"):
        await handle_update_learning_preferences(cmd, uow)


# ------------------------------------------------------------------------------
# 2. Daily Activity Handlers & FR-NEG Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_activity_records(activity_env):
    uow = activity_env["uow"]
    datetime.now(UTC)
    # Seed activities
    await uow.playbacks.record_daily_active_ms("user-01", "2026-09-01", "Asia/Ho_Chi_Minh", 600000, 15)
    await uow.playbacks.record_daily_active_ms("user-01", "2026-09-02", "Asia/Ho_Chi_Minh", 1200000, 15)

    query = GetDailyActivityQuery(user_id="user-01", from_date="2026-09-01", to_date="2026-09-05")
    records = await handle_get_daily_activity(query, uow)

    assert len(records) == 2
    assert records[0].date == "2026-09-01"
    assert records[0].active_ms == 600000
    assert not records[0].goal_met  # 10 mins < 15 mins
    assert records[1].date == "2026-09-02"
    assert records[1].active_ms == 1200000
    assert records[1].goal_met  # 20 mins >= 15 mins


@pytest.mark.asyncio
async def test_activity_keeps_same_local_date_separate_across_policy_revisions(activity_env):
    repo = activity_env["uow"].playbacks
    await repo.record_daily_active_ms(
        "user-01",
        "2026-09-02",
        "Asia/Ho_Chi_Minh",
        600000,
        15,
        policy_revision=1,
    )
    await repo.record_daily_active_ms(
        "user-01",
        "2026-09-02",
        "Asia/Tokyo",
        300000,
        5,
        policy_revision=2,
    )
    rows = await repo.get_daily_activity_range("user-01", "2026-09-02", "2026-09-02")
    assert [(row.policy_revision, row.timezone, row.goal_minutes, row.active_ms, row.goal_met) for row in rows] == [
        (1, "Asia/Ho_Chi_Minh", 15, 600000, False),
        (2, "Asia/Tokyo", 5, 300000, True),
    ]


def test_streaks_count_calendar_date_once_and_keep_yesterday_during_open_today():
    now = datetime.now(UTC)
    records = [
        LearnerDailyActivity("user-01", "2026-09-01", "Asia/Tokyo", 60000, 1, True, now, 1),
        LearnerDailyActivity("user-01", "2026-09-02", "Asia/Tokyo", 60000, 1, True, now, 1),
        LearnerDailyActivity("user-01", "2026-09-02", "Asia/Ho_Chi_Minh", 120000, 2, True, now, 2),
        LearnerDailyActivity("user-01", "2026-09-04", "Asia/Ho_Chi_Minh", 30000, 1, False, now, 2),
    ]
    assert calculate_activity_streaks(records, "2026-09-04", terminal_is_open_today=True) == (0, 2)
    assert calculate_activity_streaks(records, "2026-09-03", terminal_is_open_today=True) == (2, 2)


@pytest.mark.asyncio
async def test_get_daily_activity_range_validation(activity_env):
    uow = activity_env["uow"]

    # Exceeding 90 days
    query_wide = GetDailyActivityQuery(user_id="user-01", from_date="2026-01-01", to_date="2026-04-10")
    with pytest.raises(InvalidDomainStateError, match="Date range cannot exceed 90 days"):
        await handle_get_daily_activity(query_wide, uow)

    # from > to
    query_reversed = GetDailyActivityQuery(user_id="user-01", from_date="2026-09-10", to_date="2026-09-01")
    with pytest.raises(InvalidDomainStateError, match="from_date must be less than or equal to to_date"):
        await handle_get_daily_activity(query_reversed, uow)

    # Malformed date
    query_malformed = GetDailyActivityQuery(user_id="user-01", from_date="bad-date", to_date="2026-09-01")
    with pytest.raises(InvalidDomainStateError, match="Dates must be valid ISO format"):
        await handle_get_daily_activity(query_malformed, uow)


def make_session(
    id: str,
    user_id: str,
    catalog_item_id: str = "cat-01",
    status: PlaybackStatus = PlaybackStatus.ACTIVE,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> PlaybackSession:
    now = datetime.now(UTC)
    c_at = created_at or now
    u_at = updated_at or c_at
    return PlaybackSession(
        id=id,
        user_id=user_id,
        catalog_item_id=catalog_item_id,
        content_version_id="ver-01",
        epoch=1,
        device_class="browser",
        client_instance_id="client-01",
        status=status,
        last_seq=1,
        total_active_ms=10000,
        last_position_ms=10000,
        last_server_time=u_at,
        last_client_cumulative_ms=10000,
        created_at=c_at,
        updated_at=u_at,
        closed_at=None,
    )


# ------------------------------------------------------------------------------
# 3. Watch History & History Deletions
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watch_history_and_deletion_cutoff_isolation(activity_env):
    uow = activity_env["uow"]
    now = datetime.now(UTC)

    # Add playbacks
    p1 = make_session(
        id="play-01",
        user_id="user-01",
        catalog_item_id="cat-01",
        status=PlaybackStatus.COMPLETED,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
    )
    p2 = make_session(
        id="play-02",
        user_id="user-01",
        catalog_item_id="cat-02",
        status=PlaybackStatus.ACTIVE,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )
    await uow.playbacks.create_playback(p1)
    await uow.playbacks.create_playback(p2)

    # Initial history contains both
    history, _ = await handle_get_watch_history(GetWatchHistoryQuery(user_id="user-01"), uow)
    assert len(history) == 2
    assert history[0].playback_id == "play-02"
    assert history[1].playback_id == "play-01"

    # Request deletion (creates cutoff at now)
    del_cmd = RequestHistoryDeletionCommand(user_id="user-01")
    job = await handle_request_history_deletion(del_cmd, uow)
    assert job.status == DeletionStatus.QUEUED
    assert job.user_id == "user-01"

    # Immediately after deletion request, watch history is logically hidden!
    history_after, _ = await handle_get_watch_history(GetWatchHistoryQuery(user_id="user-01"), uow)
    assert len(history_after) == 0

    # New playback after cutoff still appears
    p3 = make_session(
        id="play-03",
        user_id="user-01",
        catalog_item_id="cat-03",
        status=PlaybackStatus.ACTIVE,
        created_at=now + timedelta(seconds=5),
        updated_at=now + timedelta(seconds=5),
    )
    await uow.playbacks.create_playback(p3)

    history_new, _ = await handle_get_watch_history(GetWatchHistoryQuery(user_id="user-01"), uow)
    assert len(history_new) == 1
    assert history_new[0].playback_id == "play-03"


@pytest.mark.asyncio
async def test_request_history_deletion_closes_active_playback(activity_env):
    uow = activity_env["uow"]
    now = datetime.now(UTC)

    # Set up active playback state
    await uow.playbacks.acquire_learner_playback_lock("user-01", "browser", "client-1")
    active_p = make_session(
        id="active-p1",
        user_id="user-01",
        catalog_item_id="cat-01",
        status=PlaybackStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    await uow.playbacks.create_playback(active_p)
    state = await uow.playbacks.acquire_learner_playback_lock("user-01", "browser", "client-1")
    state.active_playback_id = "active-p1"
    state.lease_expires_at = now + timedelta(seconds=30)
    await uow.playbacks.update_learner_playback_state(state)

    # Request history deletion
    await handle_request_history_deletion(RequestHistoryDeletionCommand(user_id="user-01"), uow)

    # Active playback must be closed and lease revoked
    p_check = await uow.playbacks.get_playback("active-p1")
    assert p_check.status == PlaybackStatus.ABANDONED
    assert p_check.closed_at is not None

    state_check = await uow.playbacks.acquire_learner_playback_lock("user-01", "browser", "client-1")
    assert state_check.active_playback_id is None


@pytest.mark.asyncio
async def test_worker_purges_playbacks_and_preserves_daily_activity_and_saved_scenes(activity_env):
    uow = activity_env["uow"]
    now = datetime.now(UTC)

    # 1. Seed playbacks & checkpoints
    p = make_session(
        id="old-play",
        user_id="user-01",
        catalog_item_id="cat-01",
        status=PlaybackStatus.COMPLETED,
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=10),
    )
    await uow.playbacks.create_playback(p)
    cp = PlaybackCheckpoint(
        user_id="user-01",
        catalog_item_id="cat-01",
        content_version_id="ver-01",
        position_ms=5000,
        updated_at=now - timedelta(minutes=10),
    )
    await uow.playbacks.save_checkpoint(cp)

    # 2. Seed daily activity, saved scene, and collection
    await uow.playbacks.record_daily_active_ms("user-01", "2026-09-01", "Asia/Ho_Chi_Minh", 1200000, 15)

    saved_scene = SavedScene(
        id="saved-sc-01",
        user_id="user-01",
        scene_id="scene-01",
        saved_at=now,
    )
    await uow.saved_scenes.add(saved_scene)

    col = PersonalCollection(
        id="col-01",
        user_id="user-01",
        name="My Favorites",
        revision=1,
        created_at=now,
        updated_at=now,
    )
    await uow.collections.create(col)

    # 3. Request deletion and run worker
    job = await handle_request_history_deletion(RequestHistoryDeletionCommand(user_id="user-01"), uow)
    processed_job = await handle_execute_history_deletion_worker(uow)

    assert processed_job is not None
    assert processed_job.id == job.id
    assert processed_job.status == DeletionStatus.COMPLETED
    assert processed_job.records_deleted == 1

    # 4. Confirm playbacks & checkpoints are purged
    assert await uow.playbacks.get_playback("old-play") is None
    assert await uow.playbacks.get_checkpoint("user-01", "cat-01") is None

    # 5. CONFIRM NON-DESTRUCTIVE RETENTION:
    # Daily activities still intact!
    daily = await uow.playbacks.get_daily_activity_range("user-01", "2026-09-01", "2026-09-01")
    assert len(daily) == 1
    assert daily[0].active_ms == 1200000

    # Saved scenes still intact!
    saved = await uow.saved_scenes.get("user-01", "scene-01")
    assert saved is not None

    # Collections still intact!
    c = await uow.collections.get_by_id("user-01", "col-01")
    assert c is not None
    assert c.name == "My Favorites"


# ------------------------------------------------------------------------------
# 4. HTTP API Contract & Integration Tests
# ------------------------------------------------------------------------------


def test_api_preferences_and_activity_lifecycle(client: TestClient, monkeypatch: pytest.MonkeyPatch, activity_env):
    uow = activity_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.activity.create_uow", lambda session: uow)

    auth_user = UserDTO(id="user-http-01", email="learner@example.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: auth_user

    # 1. GET preferences default
    res_get = client.get("/me/learning-preferences")
    assert res_get.status_code == 200
    pref_data = res_get.json()
    assert pref_data["daily_goal_minutes"] == 15
    assert pref_data["preferred_topic_ids"] == []
    assert pref_data["revision"] == 1

    # 2. PUT preferences update
    res_put = client.put(
        "/me/learning-preferences",
        json={
            "expected_revision": 1,
            "daily_goal_minutes": 30,
            "preferred_topic_ids": ["topic-business", "topic-tech"],
            "timezone": "Asia/Tokyo",
        },
    )
    assert res_put.status_code == 200
    updated = res_put.json()
    assert updated["daily_goal_minutes"] == 30
    assert updated["preferred_topic_ids"] == ["topic-business", "topic-tech"]
    assert updated["timezone"] == "Asia/Tokyo"
    assert updated["revision"] == 2

    # 3. OCC conflict on stale revision
    res_stale = client.put(
        "/me/learning-preferences",
        json={
            "expected_revision": 1,  # Stale! Current is 2
            "daily_goal_minutes": 60,
        },
    )
    assert res_stale.status_code == 409

    # 4. GET daily activity
    res_act = client.get("/me/activity?from=2026-09-01&to=2026-09-07")
    assert res_act.status_code == 200
    act_data = res_act.json()
    assert "items" in act_data
    assert "total_active_watch_seconds" in act_data
    assert "days_goal_met" in act_data
    # FR-NEG verification: zero flashcards / grammar fields
    for field in ["flashcards_reviewed", "srs_level", "grammar_points"]:
        assert field not in act_data

    # 5. GET daily activity with > 90 days range
    res_wide = client.get("/me/activity?from=2026-01-01&to=2026-06-01")
    assert res_wide.status_code == 400


def test_api_watch_history_and_deletion_lifecycle(client: TestClient, monkeypatch: pytest.MonkeyPatch, activity_env):
    uow = activity_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.activity.create_uow", lambda session: uow)

    auth_user = UserDTO(id="user-del-01", email="learner@example.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: auth_user

    # 1. GET watch history
    res_history = client.get("/me/watch-history?limit=10")
    assert res_history.status_code == 200
    assert res_history.json()["items"] == []

    # 2. DELETE watch history -> 202 Accepted
    res_del = client.delete("/me/watch-history")
    assert res_del.status_code == 202
    del_data = res_del.json()
    deletion_id = del_data["deletion_id"]
    assert del_data["status"] == "queued"
    assert "cutoff_time" in del_data

    # 3. GET deletion status
    res_status = client.get(f"/me/history-deletions/{deletion_id}")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["deletion_id"] == deletion_id
    assert status_data["user_id"] == "user-del-01"
    assert status_data["status"] == "queued"

    # 4. GET nonexistent deletion -> 404 Not Found
    res_404 = client.get("/me/history-deletions/00000000-0000-0000-0000-000000000000")
    assert res_404.status_code == 404
