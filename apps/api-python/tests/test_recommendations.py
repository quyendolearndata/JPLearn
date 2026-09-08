"""Tests for learner content recommendations (UC-L16/UC-L17, Đợt C).

Validates:
- Deterministic rule-based ranking (strategy_version: 'v1_rule_based').
- 4-Tier priority:
  1. continue_series: Next unwatched episode of a series currently in progress.
  2. preferred_topic: Published clips matching preferred_topic_ids at same CI level.
  3. same_level: Published clips at learner's current CI level.
  4. editor_pick: Fallback published clips at same level when all unwatched items are exhausted.
- Stable tie-breaker by catalog_item_id.
- Pedagogy Invariant (FR-NEG):
  - Never elevates learner's CI level (only recommends ci_level == learner.current_ci_level).
  - Never leaks title_internal (only safe title_jp or None).
  - No vocabulary or flashcard scoring.
- History cutoff isolation (FR-WAT-001):
  - Items watched before deletion cutoff_time are treated as unwatched.
- HTTP contract:
  - GET /me/recommendations with limit validation and OpenAPI strict compliance.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import UpdateLearningPreferencesCommand
from jplearn_api.application.handlers.activity import handle_update_learning_preferences
from jplearn_api.application.queries import GetRecommendationsQuery
from jplearn_api.application.handlers.recommendations import (
    handle_get_recommendations,
    STRATEGY_VERSION,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem, MediaRef
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.learning import LearnerProgress
from jplearn_api.domain.playback import (
    DeletionStatus,
    HistoryDeletionJob,
    PlaybackSession,
    PlaybackStatus,
)
from jplearn_api.domain.recommendation import RecommendationReason
from jplearn_api.domain.series import Series, SeriesItem
from jplearn_api.entrypoints.http.security import require_user
from fakes import (
    FakeCatalogRepository,
    FakeContentRepository,
    FakeLearningRepository,
    FakePlaybackRepository,
    FakeSeriesRepository,
    FakeUnitOfWork,
)


@pytest.fixture
def recommendation_env():
    catalog_repo = FakeCatalogRepository()
    content_repo = FakeContentRepository()
    learning_repo = FakeLearningRepository()
    playback_repo = FakePlaybackRepository()
    series_repo = FakeSeriesRepository()

    uow = FakeUnitOfWork(
        catalog=catalog_repo,
        content=content_repo,
        learning=learning_repo,
        playbacks=playback_repo,
        series=series_repo,
    )
    return {
        "uow": uow,
        "catalog": catalog_repo,
        "content": content_repo,
        "learning": learning_repo,
        "playbacks": playback_repo,
        "series": series_repo,
    }


def make_catalog_item(
    item_id: str,
    ci_level: int = 1,
    topic_id: str = "topic-general",
    title_internal: str = "Internal Staff Title",
    status: str = "published",
) -> CatalogItem:
    item = CatalogItem(
        id=item_id,
        topic_id=topic_id,
        ci_level=ci_level,
        duration_seconds=120,
        media_type="clip",
        visual_support="full",
        title_internal=title_internal,
        created_by="staff-01",
        status=status,
    )
    item.media.append(MediaRef(id=f"media-{item_id}", storage_key=f"raw/{item_id}.mp4"))
    return item


def make_content_version_with_scene(
    item_id: str,
    title_jp: str = "こんにちは世界",
) -> ContentVersion:
    cv = ContentVersion(
        id=f"cv-{item_id}",
        catalog_item_id=item_id,
        version_number=1,
        is_published=True,
    )
    cv.scenes.append(
        Scene(
            id=f"sc-{item_id}",
            scene_index=1,
            start_time_seconds=0,
            end_time_seconds=60,
            title_jp=title_jp,
            transcript_jp="テストスクリプト",
        )
    )
    return cv


def make_session(
    id: str,
    user_id: str,
    catalog_item_id: str,
    status: PlaybackStatus = PlaybackStatus.COMPLETED,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> PlaybackSession:
    now = datetime.now(timezone.utc)
    c_at = created_at or now
    u_at = updated_at or c_at
    return PlaybackSession(
        id=id,
        user_id=user_id,
        catalog_item_id=catalog_item_id,
        content_version_id=f"ver-{catalog_item_id}",
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
# 1. Continue Series Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_continue_series_recommends_next_episode(recommendation_env):
    uow = recommendation_env["uow"]
    user_id = "learner-01"

    # Set learner CI level = 1
    uow.learning.progress[user_id] = LearnerProgress(user_id=user_id, current_ci_level=1)

    # Catalog items for series
    ep1 = make_catalog_item("series-ep-01", ci_level=1)
    ep2 = make_catalog_item("series-ep-02", ci_level=1)
    ep3 = make_catalog_item("series-ep-03", ci_level=1)
    await uow.catalog.add(ep1)
    await uow.catalog.add(ep2)
    await uow.catalog.add(ep3)

    # Series setup
    series = Series(
        id="series-01",
        title="Anime Daily Life",
        description="Daily life in Tokyo",
        ci_level="1",
        topic_id="topic-general",
        status="published",
        items=[
            SeriesItem(catalog_item_id="series-ep-01", position=1),
            SeriesItem(catalog_item_id="series-ep-02", position=2),
            SeriesItem(catalog_item_id="series-ep-03", position=3),
        ],
    )
    await uow.series.add(series)

    # Learner watched ep 1
    session = make_session(
        id="sess-01",
        user_id=user_id,
        catalog_item_id="series-ep-01",
        status=PlaybackStatus.COMPLETED,
    )
    await uow.playbacks.create_playback(session)

    query = GetRecommendationsQuery(user_id=user_id, limit=10)
    items, strategy = await handle_get_recommendations(query, uow)

    assert strategy == STRATEGY_VERSION
    assert len(items) >= 1
    # First item must be ep 2 with continue_series
    top_rec = items[0]
    assert top_rec.catalog_item_id == "series-ep-02"
    assert top_rec.reason == RecommendationReason.CONTINUE_SERIES
    assert top_rec.series_id == "series-01"
    assert top_rec.series_title == "Anime Daily Life"


# ------------------------------------------------------------------------------
# 2. Preferred Topic Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preferred_topic_prioritized_over_generic_same_level(recommendation_env):
    uow = recommendation_env["uow"]
    user_id = "learner-02"

    uow.learning.progress[user_id] = LearnerProgress(user_id=user_id, current_ci_level=2)
    uow.learning.commit_transaction()

    # User preferences: prefers topic-tech
    cmd = UpdateLearningPreferencesCommand(
        user_id=user_id,
        expected_revision=1,
        daily_goal_minutes=15,
        preferred_topic_ids=["topic-tech"],
        timezone="Asia/Tokyo",
    )
    await handle_update_learning_preferences(cmd, uow)

    # Catalog: 1 item in topic-tech, 1 item in topic-sports, both level 2
    item_tech = make_catalog_item("clip-tech-01", ci_level=2, topic_id="topic-tech")
    item_sports = make_catalog_item("clip-sports-01", ci_level=2, topic_id="topic-sports")
    await uow.catalog.add(item_tech)
    await uow.catalog.add(item_sports)

    query = GetRecommendationsQuery(user_id=user_id, limit=10)
    items, _ = await handle_get_recommendations(query, uow)

    assert len(items) == 2
    assert items[0].catalog_item_id == "clip-tech-01"
    assert items[0].reason == RecommendationReason.PREFERRED_TOPIC

    assert items[1].catalog_item_id == "clip-sports-01"
    assert items[1].reason == RecommendationReason.SAME_LEVEL


# ------------------------------------------------------------------------------
# 3. Same Level and Editor Pick Fallback Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_same_level_and_editor_pick_fallback(recommendation_env):
    uow = recommendation_env["uow"]
    user_id = "learner-03"

    uow.learning.progress[user_id] = LearnerProgress(user_id=user_id, current_ci_level=1)

    item1 = make_catalog_item("clip-01", ci_level=1)
    item2 = make_catalog_item("clip-02", ci_level=1)
    await uow.catalog.add(item1)
    await uow.catalog.add(item2)

    # Learner has watched item1
    session = make_session(
        id="sess-02",
        user_id=user_id,
        catalog_item_id="clip-01",
        status=PlaybackStatus.ACTIVE,
    )
    await uow.playbacks.create_playback(session)

    # Query with limit 2: item2 should be SAME_LEVEL, item1 should be fallback EDITOR_PICK
    query = GetRecommendationsQuery(user_id=user_id, limit=2)
    items, _ = await handle_get_recommendations(query, uow)

    assert len(items) == 2
    assert items[0].catalog_item_id == "clip-02"
    assert items[0].reason == RecommendationReason.SAME_LEVEL

    assert items[1].catalog_item_id == "clip-01"
    assert items[1].reason == RecommendationReason.EDITOR_PICK


# ------------------------------------------------------------------------------
# 4. Strict Pedagogical Invariant (FR-NEG) & Privacy Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fr_neg_never_recommends_higher_ci_level(recommendation_env):
    uow = recommendation_env["uow"]
    user_id = "learner-beginner"

    # Learner is CI level 1
    uow.learning.progress[user_id] = LearnerProgress(user_id=user_id, current_ci_level=1)

    # Add items of levels 1, 2, 3, 4
    await uow.catalog.add(make_catalog_item("clip-lvl1", ci_level=1))
    await uow.catalog.add(make_catalog_item("clip-lvl2", ci_level=2))
    await uow.catalog.add(make_catalog_item("clip-lvl3", ci_level=3))
    await uow.catalog.add(make_catalog_item("clip-lvl4", ci_level=4))

    query = GetRecommendationsQuery(user_id=user_id, limit=10)
    items, _ = await handle_get_recommendations(query, uow)

    # Only level 1 item should be recommended
    assert len(items) == 1
    assert items[0].catalog_item_id == "clip-lvl1"
    assert items[0].ci_level == 1
    for it in items:
        assert it.ci_level == 1


@pytest.mark.asyncio
async def test_fr_neg_no_internal_title_exposure(recommendation_env):
    uow = recommendation_env["uow"]
    user_id = "learner-privacy"

    item = make_catalog_item(
        "clip-secret",
        ci_level=1,
        title_internal="SECRET_INTERNAL_STAFF_TITLE_DO_NOT_LEAK",
    )
    await uow.catalog.add(item)

    # Add content version with public Japanese scene title
    cv = make_content_version_with_scene("clip-secret", title_jp="初めまして")
    uow.content.versions["clip-secret"] = [cv]

    query = GetRecommendationsQuery(user_id=user_id, limit=5)
    items, _ = await handle_get_recommendations(query, uow)

    assert len(items) == 1
    rec = items[0]
    assert rec.title_jp == "初めまして"
    # Verify title_internal is completely absent on the projection
    assert not hasattr(rec, "title_internal")


# ------------------------------------------------------------------------------
# 5. History Cutoff Isolation Tests (FR-WAT-001)
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cutoff_isolation_resets_series_progress(recommendation_env):
    uow = recommendation_env["uow"]
    user_id = "learner-cutoff"

    uow.learning.progress[user_id] = LearnerProgress(user_id=user_id, current_ci_level=1)

    ep1 = make_catalog_item("cut-ep-01", ci_level=1)
    ep2 = make_catalog_item("cut-ep-02", ci_level=1)
    await uow.catalog.add(ep1)
    await uow.catalog.add(ep2)

    series = Series(
        id="series-cut",
        title="Cutoff Series",
        description="Testing cutoff isolation",
        ci_level="1",
        topic_id="topic-general",
        status="published",
        items=[
            SeriesItem(catalog_item_id="cut-ep-01", position=1),
            SeriesItem(catalog_item_id="cut-ep-02", position=2),
        ],
    )
    await uow.series.add(series)

    # User watched ep1 2 hours ago
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    session = make_session(
        id="sess-old",
        user_id=user_id,
        catalog_item_id="cut-ep-01",
        status=PlaybackStatus.COMPLETED,
        created_at=past_time,
        updated_at=past_time,
    )
    await uow.playbacks.create_playback(session)

    # User requested deletion 1 hour ago (cutoff = past_time + 1h)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    now = datetime.now(timezone.utc)
    job = HistoryDeletionJob(
        id="del-job-01",
        user_id=user_id,
        status=DeletionStatus.QUEUED,
        cutoff_time=cutoff,
        records_deleted=0,
        attempts=0,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    await uow.playbacks.create_history_deletion_job(job)

    # When requesting recommendations, ep1 is excluded from active watched items
    # Therefore, continue_series does NOT jump to ep2; both ep1 and ep2 are available as SAME_LEVEL
    query = GetRecommendationsQuery(user_id=user_id, limit=5)
    items, _ = await handle_get_recommendations(query, uow)

    # First item by stable tie-breaker ID will be cut-ep-01 as SAME_LEVEL
    assert len(items) == 2
    assert items[0].catalog_item_id == "cut-ep-01"
    assert items[0].reason == RecommendationReason.SAME_LEVEL
    assert items[1].catalog_item_id == "cut-ep-02"
    assert items[1].reason == RecommendationReason.SAME_LEVEL


# ------------------------------------------------------------------------------
# 6. HTTP API Endpoint Contract Tests
# ------------------------------------------------------------------------------

def test_api_recommendations_endpoint_unauthorized(client: TestClient):
    # Without auth token -> 401
    res = client.get("/me/recommendations")
    assert res.status_code == 401


def test_api_recommendations_endpoint_success(client: TestClient, monkeypatch: pytest.MonkeyPatch, recommendation_env):
    uow = recommendation_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.recommendations.create_uow", lambda session: uow)

    user_id = "user-rec-http"
    auth_user = UserDTO(id=user_id, email="rec@example.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: auth_user

    uow.learning.progress[user_id] = LearnerProgress(user_id=user_id, current_ci_level=1)

    item1 = make_catalog_item("rec-http-01", ci_level=1, topic_id="topic-anime")
    cv1 = make_content_version_with_scene("rec-http-01", title_jp="アニメシーン")
    uow.content.versions["rec-http-01"] = [cv1]

    item2 = make_catalog_item("rec-http-02", ci_level=1, topic_id="topic-business")
    uow.catalog.items["rec-http-01"] = item1
    uow.catalog.items["rec-http-02"] = item2

    res = client.get("/me/recommendations?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert data["strategy_version"] == "v1_rule_based"
    assert "items" in data
    assert len(data["items"]) == 2

    first = data["items"][0]
    assert first["catalog_item_id"] == "rec-http-01"
    assert first["title_jp"] == "アニメシーン"
    assert first["ci_level"] == 1
    assert "title_internal" not in first


def test_api_recommendations_endpoint_limit_validation(client: TestClient, monkeypatch: pytest.MonkeyPatch, recommendation_env):
    uow = recommendation_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.recommendations.create_uow", lambda session: uow)

    user_id = "user-rec-limit"
    auth_user = UserDTO(id=user_id, email="limit@example.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: auth_user

    # Limit exceeds maximum 50 defined in OpenAPI query schema -> 400 Bad Request
    res = client.get("/me/recommendations?limit=60")
    assert res.status_code == 400
