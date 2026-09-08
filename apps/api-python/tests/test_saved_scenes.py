"""Unit, handler, and contract tests for Saved Scenes (PR3 / ADR-007 / UC-L16)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from fakes import (
    FakeCatalogRepository,
    FakeContentRepository,
    FakeSavedSceneRepository,
    FakeUnitOfWork,
)
from jplearn_api.application.commands import (
    DeleteSavedSceneCommand,
    SaveSceneCommand,
)
from jplearn_api.application.handlers.saved_scenes import (
    handle_delete_saved_scene,
    handle_list_saved_scenes,
    handle_save_scene,
)
from jplearn_api.application.queries import ListSavedScenesQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.domain.saved_scene import SavedScene, SceneAvailability
from jplearn_api.entrypoints.http.security import require_user


def _add_version(content_repo: FakeContentRepository, version: ContentVersion) -> None:
    content_repo._committed_versions.setdefault(version.catalog_item_id, []).append(version)
    content_repo.versions = copy.deepcopy(content_repo._committed_versions)


def _add_catalog_item(catalog_repo: FakeCatalogRepository, item: CatalogItem) -> None:
    catalog_repo._committed_items[item.id] = item
    catalog_repo.items[item.id] = item


@pytest.fixture(autouse=True)
def _enable_capabilities(client: TestClient):
    client.app.state.settings.video_scene_breakdown_enabled = True
    yield
    client.app.state.settings.video_scene_breakdown_enabled = False


# ------------------------------------------------------------------------------
# 1. Domain Tests
# ------------------------------------------------------------------------------


def test_saved_scene_domain_creation_and_enum():
    saved = SavedScene(
        id="saved-01",
        user_id="user-01",
        scene_id="scene-01",
        saved_at=datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC),
    )
    assert saved.id == "saved-01"
    assert saved.user_id == "user-01"
    assert saved.scene_id == "scene-01"
    assert saved.saved_at.year == 2026

    assert SceneAvailability.AVAILABLE == "available"
    assert SceneAvailability.STALE_VERSION == "stale_version"
    assert SceneAvailability.UNAVAILABLE == "unavailable"


# ------------------------------------------------------------------------------
# 2. Application Handler Tests
# ------------------------------------------------------------------------------


@pytest.fixture
def test_data():
    clip_1 = CatalogItem(
        id="clip-01",
        topic_id="topic-1",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="high",
        title_internal="Clip 1",
        created_by="teacher-01",
        status="published",
    )
    sc_1 = Scene("sc-01", 1, 0, 15, "あいさつ", "おはようございます。")
    sc_2 = Scene("sc-02", 2, 15, 30, "自己紹介", "はじめまして、田中です。")
    ver_1 = ContentVersion(
        id="ver-01",
        catalog_item_id="clip-01",
        version_number=1,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=[sc_1, sc_2],
    )

    catalog_repo = FakeCatalogRepository({"clip-01": clip_1})
    content_repo = FakeContentRepository({"ver-01": ver_1})
    saved_repo = FakeSavedSceneRepository()

    uow = FakeUnitOfWork(
        catalog=catalog_repo,
        content=content_repo,
        saved_scenes=saved_repo,
    )
    return {
        "clip_1": clip_1,
        "sc_1": sc_1,
        "sc_2": sc_2,
        "ver_1": ver_1,
        "catalog_repo": catalog_repo,
        "content_repo": content_repo,
        "saved_repo": saved_repo,
        "uow": uow,
    }


@pytest.mark.asyncio
async def test_handle_save_scene_idempotency(test_data):
    uow = test_data["uow"]

    # 1. First save -> created=True
    cmd = SaveSceneCommand(user_id="user-01", scene_id="sc-01")
    saved_1, created_1 = await handle_save_scene(cmd, uow)
    assert created_1 is True
    assert saved_1.user_id == "user-01"
    assert saved_1.scene_id == "sc-01"

    # 2. Second save of same scene -> created=False, saved_at preserved
    saved_2, created_2 = await handle_save_scene(cmd, uow)
    assert created_2 is False
    assert saved_2.id == saved_1.id
    assert saved_2.saved_at == saved_1.saved_at


@pytest.mark.asyncio
async def test_handle_save_scene_rejections(test_data):
    uow = test_data["uow"]
    content_repo = test_data["content_repo"]
    catalog_repo = test_data["catalog_repo"]

    # Non-existent scene
    with pytest.raises(EntityNotFoundError, match="Scene non-existent not found"):
        await handle_save_scene(SaveSceneCommand("user-01", "non-existent"), uow)

    # Unpublished version
    draft_sc = Scene("sc-draft", 1, 0, 10, "下書き", "下書きシーン")
    draft_ver = ContentVersion(
        id="ver-draft",
        catalog_item_id="clip-01",
        version_number=2,
        is_published=False,
        scenes=[draft_sc],
    )
    _add_version(content_repo, draft_ver)
    with pytest.raises(InvalidDomainStateError, match="unpublished content version"):
        await handle_save_scene(SaveSceneCommand("user-01", "sc-draft"), uow)

    # Unpublished catalog item
    draft_clip = CatalogItem(
        id="clip-draft",
        topic_id="topic-1",
        ci_level=1,
        duration_seconds=30,
        media_type="video",
        visual_support="high",
        title_internal="Draft Clip",
        created_by="staff",
        status="draft",
    )
    sc_draft_clip = Scene("sc-dc", 1, 0, 10, "タイトル", "本文")
    ver_dc = ContentVersion(
        id="ver-dc",
        catalog_item_id="clip-draft",
        version_number=1,
        is_published=True,
        scenes=[sc_draft_clip],
    )
    _add_catalog_item(catalog_repo, draft_clip)
    _add_version(content_repo, ver_dc)
    with pytest.raises(InvalidDomainStateError, match="unpublished catalog item"):
        await handle_save_scene(SaveSceneCommand("user-01", "sc-dc"), uow)


@pytest.mark.asyncio
async def test_handle_save_scene_rejects_outdated_version(test_data):
    uow = test_data["uow"]
    content_repo = test_data["content_repo"]

    # Clip 1 publishes v2
    sc_v2 = Scene("sc-v2", 1, 0, 20, "新バージョン", "新しいテキスト")
    ver_2 = ContentVersion(
        id="ver-02",
        catalog_item_id="clip-01",
        version_number=2,
        is_published=True,
        scenes=[sc_v2],
    )
    _add_version(content_repo, ver_2)

    # Saving scene from v1 should be rejected as outdated
    with pytest.raises(InvalidDomainStateError, match="outdated content version"):
        await handle_save_scene(SaveSceneCommand("user-01", "sc-01"), uow)

    # Saving scene from v2 succeeds
    saved, created = await handle_save_scene(SaveSceneCommand("user-01", "sc-v2"), uow)
    assert created is True
    assert saved.scene_id == "sc-v2"


@pytest.mark.asyncio
async def test_handle_delete_saved_scene_idempotent(test_data):
    uow = test_data["uow"]

    # Save first
    await handle_save_scene(SaveSceneCommand("user-01", "sc-01"), uow)

    # Delete existing -> succeeds
    await handle_delete_saved_scene(DeleteSavedSceneCommand("user-01", "sc-01"), uow)

    # Delete non-existent or already deleted -> succeeds idempotently
    await handle_delete_saved_scene(DeleteSavedSceneCommand("user-01", "sc-01"), uow)
    await handle_delete_saved_scene(DeleteSavedSceneCommand("user-01", "never-saved"), uow)


@pytest.mark.asyncio
async def test_handle_list_saved_scenes_availability_and_stale_handling(test_data):
    uow = test_data["uow"]
    content_repo = test_data["content_repo"]
    catalog_repo = test_data["catalog_repo"]

    # 1. Save sc-01 while v1 is current
    await handle_save_scene(SaveSceneCommand("user-01", "sc-01"), uow)

    # 2. Clip 1 publishes v2 -> sc-01 becomes stale_version
    sc_v2 = Scene("sc-v2", 1, 0, 20, "新バージョン", "新しいテキスト")
    ver_2 = ContentVersion(
        id="ver-02",
        catalog_item_id="clip-01",
        version_number=2,
        is_published=True,
        scenes=[sc_v2],
    )
    _add_version(content_repo, ver_2)

    # 3. Save sc-v2 as current version
    await handle_save_scene(SaveSceneCommand("user-01", "sc-v2"), uow)

    # 4. List saved scenes
    projections, total = await handle_list_saved_scenes(
        ListSavedScenesQuery(user_id="user-01", offset=0, limit=10),
        uow,
    )
    assert total == 2
    assert len(projections) == 2

    # Map by scene_id
    proj_map = {p.scene_id: p for p in projections}

    # sc-v2 is available
    assert proj_map["sc-v2"].availability == "available"
    assert proj_map["sc-v2"].title_jp == "新バージョン"
    assert proj_map["sc-v2"].transcript_jp == "新しいテキスト"

    # sc-01 is stale_version (not automatically shifted to v2 timing!)
    assert proj_map["sc-01"].availability == "stale_version"
    assert proj_map["sc-01"].start_time_seconds == 0
    assert proj_map["sc-01"].end_time_seconds == 15
    assert proj_map["sc-01"].title_jp == "あいさつ"
    assert proj_map["sc-01"].transcript_jp == "おはようございます。"

    # 5. Simulate catalog item unpublished -> becomes unavailable
    catalog_repo._committed_items["clip-01"].status = "draft"
    catalog_repo.items["clip-01"].status = "draft"
    projections_unpub, _ = await handle_list_saved_scenes(
        ListSavedScenesQuery(user_id="user-01", offset=0, limit=10),
        uow,
    )
    for p in projections_unpub:
        assert p.availability == "unavailable"
        assert p.unavailable_reason == "catalog_unpublished"
        # Minimum stub: no transcript, no timing exposure
        assert p.title_jp is None
        assert p.transcript_jp is None
        assert p.start_time_seconds is None


# ------------------------------------------------------------------------------
# 3. HTTP API Contract & Integration Tests
# ------------------------------------------------------------------------------


def test_api_saved_scenes_put_get_delete_lifecycle(client: TestClient, monkeypatch: pytest.MonkeyPatch, test_data):
    uow = test_data["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.saved_scenes.create_uow", lambda session: uow)

    user = UserDTO(id="user-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: user

    # 1. PUT /me/saved-scenes/{scene_id} -> 201 Created first time
    res_1 = client.put("/me/saved-scenes/sc-01")
    assert res_1.status_code == 201
    body_1 = res_1.json()
    assert body_1["scene_id"] == "sc-01"
    assert "saved_at" in body_1

    # 2. PUT /me/saved-scenes/{scene_id} again -> 200 OK idempotent
    res_2 = client.put("/me/saved-scenes/sc-01")
    assert res_2.status_code == 200
    body_2 = res_2.json()
    assert body_2["id"] == body_1["id"]
    assert body_2["saved_at"] == body_1["saved_at"]

    # 3. GET /me/saved-scenes -> 200 OK with availability
    res_list = client.get("/me/saved-scenes")
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) == 1
    assert items[0]["scene_id"] == "sc-01"
    assert items[0]["availability"] == "available"
    assert items[0]["title_jp"] == "あいさつ"
    assert items[0]["transcript_jp"] == "おはようございます。"

    # 4. DELETE /me/saved-scenes/{scene_id} -> 204 No Content
    res_del_1 = client.delete("/me/saved-scenes/sc-01")
    assert res_del_1.status_code == 204

    # 5. DELETE again -> 204 No Content idempotent
    res_del_2 = client.delete("/me/saved-scenes/sc-01")
    assert res_del_2.status_code == 204

    # 6. GET /me/saved-scenes -> empty list
    res_list_after = client.get("/me/saved-scenes")
    assert res_list_after.status_code == 200
    assert res_list_after.json() == []


def test_api_saved_scenes_user_isolation(client: TestClient, monkeypatch: pytest.MonkeyPatch, test_data):
    uow = test_data["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.saved_scenes.create_uow", lambda session: uow)

    user_a = UserDTO(id="user-a", email="a@test.com", roles=["learner"])
    user_b = UserDTO(id="user-b", email="b@test.com", roles=["learner"])

    # User A saves scene
    client.app.dependency_overrides[require_user] = lambda: user_a
    res_save = client.put("/me/saved-scenes/sc-01")
    assert res_save.status_code == 201

    # User B lists saved scenes -> empty
    client.app.dependency_overrides[require_user] = lambda: user_b
    res_b_list = client.get("/me/saved-scenes")
    assert res_b_list.status_code == 200
    assert res_b_list.json() == []

    # User B deletes sc-01 -> 204 (idempotent, doesn't affect User A)
    res_b_del = client.delete("/me/saved-scenes/sc-01")
    assert res_b_del.status_code == 204

    # User A lists saved scenes -> still has sc-01
    client.app.dependency_overrides[require_user] = lambda: user_a
    res_a_list = client.get("/me/saved-scenes")
    assert res_a_list.status_code == 200
    assert len(res_a_list.json()) == 1


def test_api_saved_scenes_unauthenticated(client: TestClient):
    client.app.dependency_overrides.clear()
    assert client.put("/me/saved-scenes/sc-01").status_code == 401
    assert client.get("/me/saved-scenes").status_code == 401
    assert client.delete("/me/saved-scenes/sc-01").status_code == 401
