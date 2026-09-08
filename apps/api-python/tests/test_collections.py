"""Unit, handler, and contract tests for Personal Collections (PR3a / ADR-007 / UC-L23)."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    CreateCollectionCommand,
    DeleteCollectionCommand,
    DeleteSavedSceneCommand,
    PatchCollectionCommand,
    SaveSceneCommand,
    UpdateCollectionScenesCommand,
)
from jplearn_api.application.handlers.collections import (
    MAX_COLLECTIONS_PER_USER,
    MAX_SCENES_PER_COLLECTION,
    handle_create_collection,
    handle_delete_collection,
    handle_get_collection,
    handle_list_collections,
    handle_patch_collection,
    handle_update_collection_scenes,
)
from jplearn_api.application.handlers.saved_scenes import (
    handle_delete_saved_scene,
    handle_save_scene,
)
from jplearn_api.application.queries import GetCollectionQuery, ListCollectionsQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.collection import (
    CollectionDetail,
    CollectionSceneDetail,
    PersonalCollection,
)
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.domain.saved_scene import SavedScene, SceneAvailability
from jplearn_api.entrypoints.http.security import require_user
from fakes import (
    FakeCatalogRepository,
    FakeCollectionRepository,
    FakeContentRepository,
    FakeSavedSceneRepository,
    FakeUnitOfWork,
)


def _add_version(content_repo: FakeContentRepository, version: ContentVersion) -> None:
    content_repo._committed_versions.setdefault(version.catalog_item_id, []).append(version)
    content_repo.versions = copy.deepcopy(content_repo._committed_versions)


def _add_catalog_item(catalog_repo: FakeCatalogRepository, item: CatalogItem) -> None:
    catalog_repo._committed_items[item.id] = item
    catalog_repo.items[item.id] = item


@pytest.fixture(autouse=True)
def _enable_capabilities(client: TestClient):
    client.app.state.settings.personal_collections_enabled = True
    client.app.state.settings.video_scene_breakdown_enabled = True
    yield
    client.app.state.settings.personal_collections_enabled = False
    client.app.state.settings.video_scene_breakdown_enabled = False


# ------------------------------------------------------------------------------
# 1. Domain Tests
# ------------------------------------------------------------------------------

def test_personal_collection_domain_creation():
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    coll = PersonalCollection(
        id="col-01",
        user_id="user-01",
        name="Tình huống chào hỏi",
        revision=1,
        created_at=now,
        updated_at=now,
        scene_count=0,
    )
    assert coll.id == "col-01"
    assert coll.user_id == "user-01"
    assert coll.name == "Tình huống chào hỏi"
    assert coll.revision == 1
    assert coll.scene_count == 0


def test_collection_detail_domain_creation():
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    sc_detail = CollectionSceneDetail(
        position=0,
        scene_id="sc-01",
        availability=SceneAvailability.AVAILABLE,
        scene={"title_jp": "挨拶"},
        reason=None,
        added_at=now,
    )
    detail = CollectionDetail(
        id="col-01",
        user_id="user-01",
        name="Tình huống chào hỏi",
        revision=1,
        scene_count=1,
        created_at=now,
        updated_at=now,
        scenes=[sc_detail],
    )
    assert detail.scene_count == 1
    assert detail.scenes[0].scene_id == "sc-01"
    assert detail.scenes[0].availability == SceneAvailability.AVAILABLE


# ------------------------------------------------------------------------------
# 2. Application Handler Tests
# ------------------------------------------------------------------------------

@pytest.fixture
def test_env():
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
    coll_repo = FakeCollectionRepository()

    uow = FakeUnitOfWork(
        catalog=catalog_repo,
        content=content_repo,
        saved_scenes=saved_repo,
        collections=coll_repo,
    )

    return {
        "uow": uow,
        "catalog_repo": catalog_repo,
        "content_repo": content_repo,
        "saved_repo": saved_repo,
        "coll_repo": coll_repo,
    }


@pytest.mark.asyncio
async def test_create_collection_handler(test_env):
    uow = test_env["uow"]

    # 1. Valid creation
    coll, created = await handle_create_collection(
        CreateCollectionCommand(user_id="user-01", name="Học giao tiếp"),
        uow,
    )
    assert created is True
    assert coll.name == "Học giao tiếp"
    assert coll.revision == 1
    assert coll.user_id == "user-01"

    # 2. Replay with same idempotency key and name -> created=False
    coll_replay, created_replay = await handle_create_collection(
        CreateCollectionCommand(user_id="user-01", name="Bộ sưu tập 2", idempotency_key="key-1"),
        uow,
    )
    assert created_replay is True

    coll_replay2, created_replay2 = await handle_create_collection(
        CreateCollectionCommand(user_id="user-01", name="Bộ sưu tập 2", idempotency_key="key-1"),
        uow,
    )
    assert created_replay2 is False
    assert coll_replay2.id == coll_replay.id

    # 3. Replay with same key but different name -> ConflictError
    with pytest.raises(ConflictError, match="Idempotency key reused with different"):
        await handle_create_collection(
            CreateCollectionCommand(user_id="user-01", name="Tên khác", idempotency_key="key-1"),
            uow,
        )

    # 4. Name validations (empty, whitespace, > 80 chars)
    with pytest.raises(InvalidDomainStateError, match="between 1 and 80 characters"):
        await handle_create_collection(CreateCollectionCommand(user_id="user-01", name="   "), uow)

    with pytest.raises(InvalidDomainStateError, match="between 1 and 80 characters"):
        await handle_create_collection(CreateCollectionCommand(user_id="user-01", name="A" * 81), uow)


@pytest.mark.asyncio
async def test_collection_quota_handler(test_env):
    uow = test_env["uow"]

    # Create 50 collections
    for i in range(MAX_COLLECTIONS_PER_USER):
        await handle_create_collection(
            CreateCollectionCommand(user_id="user-01", name=f"Collection {i+1}"),
            uow,
        )

    # 51st creation must fail with quota error
    with pytest.raises(InvalidDomainStateError, match="Maximum limit of 50 collections reached"):
        await handle_create_collection(
            CreateCollectionCommand(user_id="user-01", name="Collection 51"),
            uow,
        )


@pytest.mark.asyncio
async def test_patch_and_update_scenes_occ(test_env):
    uow = test_env["uow"]

    # 1. Save sc-01 and sc-02 first
    await handle_save_scene(SaveSceneCommand(user_id="user-01", scene_id="sc-01"), uow)
    await handle_save_scene(SaveSceneCommand(user_id="user-01", scene_id="sc-02"), uow)

    # 2. Create collection
    coll, _ = await handle_create_collection(
        CreateCollectionCommand(user_id="user-01", name="My Collection"),
        uow,
    )
    assert coll.revision == 1

    # 3. Patch name with matching expected_revision
    patched = await handle_patch_collection(
        PatchCollectionCommand(
            user_id="user-01",
            collection_id=coll.id,
            expected_revision=1,
            name="Renamed Collection",
        ),
        uow,
    )
    assert patched.name == "Renamed Collection"
    assert patched.revision == 2

    # 4. Patch with stale expected_revision -> ConflictError
    with pytest.raises(ConflictError, match="Collection revision conflict"):
        await handle_patch_collection(
            PatchCollectionCommand(
                user_id="user-01",
                collection_id=coll.id,
                expected_revision=1,
                name="Stale Rename",
            ),
            uow,
        )

    # 5. Update scenes with expected_revision=2
    updated_scenes = await handle_update_collection_scenes(
        UpdateCollectionScenesCommand(
            user_id="user-01",
            collection_id=coll.id,
            expected_revision=2,
            scene_ids=["sc-02", "sc-01"],
        ),
        uow,
    )
    assert updated_scenes.revision == 3
    assert updated_scenes.scene_count == 2

    # 6. Reject scene not in saved_scenes
    with pytest.raises(InvalidDomainStateError, match="not saved"):
        await handle_update_collection_scenes(
            UpdateCollectionScenesCommand(
                user_id="user-01",
                collection_id=coll.id,
                expected_revision=3,
                scene_ids=["sc-unsaved"],
            ),
            uow,
        )

    # 7. Reject duplicate scenes in request
    with pytest.raises(InvalidDomainStateError, match="Duplicate scenes"):
        await handle_update_collection_scenes(
            UpdateCollectionScenesCommand(
                user_id="user-01",
                collection_id=coll.id,
                expected_revision=3,
                scene_ids=["sc-01", "sc-01"],
            ),
            uow,
        )

    # 8. Reject > 200 scenes
    with pytest.raises(InvalidDomainStateError, match="Maximum of 200 scenes"):
        await handle_update_collection_scenes(
            UpdateCollectionScenesCommand(
                user_id="user-01",
                collection_id=coll.id,
                expected_revision=3,
                scene_ids=[f"sc-{i}" for i in range(201)],
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_saved_scene_deletion_cascades_and_bumps_collection_revision(test_env):
    uow = test_env["uow"]

    # 1. Save sc-01 and sc-02
    await handle_save_scene(SaveSceneCommand(user_id="user-01", scene_id="sc-01"), uow)
    await handle_save_scene(SaveSceneCommand(user_id="user-01", scene_id="sc-02"), uow)

    # 2. Create collection and add both scenes
    coll, _ = await handle_create_collection(
        CreateCollectionCommand(user_id="user-01", name="Collection Test"),
        uow,
    )
    await handle_update_collection_scenes(
        UpdateCollectionScenesCommand(
            user_id="user-01",
            collection_id=coll.id,
            expected_revision=1,
            scene_ids=["sc-01", "sc-02"],
        ),
        uow,
    )

    detail_before = await handle_get_collection(
        GetCollectionQuery(user_id="user-01", collection_id=coll.id),
        uow,
    )
    assert detail_before.scene_count == 2
    assert detail_before.revision == 2

    # 3. Delete saved scene sc-01
    await handle_delete_saved_scene(
        DeleteSavedSceneCommand(user_id="user-01", scene_id="sc-01"),
        uow,
    )

    # 4. Collection detail must now only have sc-02, and revision bumped to 3!
    detail_after = await handle_get_collection(
        GetCollectionQuery(user_id="user-01", collection_id=coll.id),
        uow,
    )
    assert detail_after.scene_count == 1
    assert detail_after.revision == 3
    assert detail_after.scenes[0].scene_id == "sc-02"
    assert detail_after.scenes[0].position == 0


# ------------------------------------------------------------------------------
# 3. HTTP API Contract & Integration Tests
# ------------------------------------------------------------------------------

def test_api_collections_full_lifecycle(client: TestClient, monkeypatch: pytest.MonkeyPatch, test_env):
    uow = test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.collections.create_uow", lambda session: uow)
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.saved_scenes.create_uow", lambda session: uow)

    user = UserDTO(id="user-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: user

    # 1. Save sc-01
    res_save = client.put("/me/saved-scenes/sc-01")
    assert res_save.status_code in (200, 201)

    # 2. POST /me/collections -> 201 Created
    res_create = client.post(
        "/me/collections",
        json={"name": "Hội thoại mẫu"},
        headers={"Idempotency-Key": "create-key-1"},
    )
    assert res_create.status_code == 201
    coll_data = res_create.json()
    coll_id = coll_data["id"]
    assert coll_data["name"] == "Hội thoại mẫu"
    assert coll_data["revision"] == 1
    assert coll_data["scene_count"] == 0

    # 3. Replay creation with same key -> 200 OK
    res_replay = client.post(
        "/me/collections",
        json={"name": "Hội thoại mẫu"},
        headers={"Idempotency-Key": "create-key-1"},
    )
    assert res_replay.status_code == 200
    assert res_replay.json()["id"] == coll_id

    # 4. GET /me/collections -> 200 OK list
    res_list = client.get("/me/collections")
    assert res_list.status_code == 200
    colls = res_list.json()
    assert len(colls) == 1
    assert colls[0]["id"] == coll_id

    # 5. PUT /me/collections/{id}/scenes -> add sc-01
    res_put_scenes = client.put(
        f"/me/collections/{coll_id}/scenes",
        json={"expected_revision": 1, "scene_ids": ["sc-01"]},
    )
    assert res_put_scenes.status_code == 200
    assert res_put_scenes.json()["revision"] == 2
    assert res_put_scenes.json()["scene_count"] == 1

    # 6. GET /me/collections/{id} -> detail with scene & availability
    res_detail = client.get(f"/me/collections/{coll_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["name"] == "Hội thoại mẫu"
    assert detail["revision"] == 2
    assert len(detail["scenes"]) == 1
    assert detail["scenes"][0]["scene_id"] == "sc-01"
    assert detail["scenes"][0]["availability"] == "available"
    assert detail["scenes"][0]["title_jp"] == "あいさつ"

    # 7. PATCH /me/collections/{id} -> rename
    res_patch = client.patch(
        f"/me/collections/{coll_id}",
        json={"expected_revision": 2, "name": "Hội thoại nâng cao"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["name"] == "Hội thoại nâng cao"
    assert res_patch.json()["revision"] == 3

    # 8. DELETE /me/collections/{id} -> 204 No Content
    res_del = client.delete(f"/me/collections/{coll_id}")
    assert res_del.status_code == 204

    # 9. GET /me/collections/{id} -> 404 Not Found
    res_detail_del = client.get(f"/me/collections/{coll_id}")
    assert res_detail_del.status_code == 404

    # 10. Saved scene sc-01 must still be intact!
    res_saved = client.get("/me/saved-scenes")
    assert res_saved.status_code == 200
    assert len(res_saved.json()) == 1


def test_api_collections_user_isolation(client: TestClient, monkeypatch: pytest.MonkeyPatch, test_env):
    uow = test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.collections.create_uow", lambda session: uow)

    user_a = UserDTO(id="user-a", email="a@test.com", roles=["learner"])
    user_b = UserDTO(id="user-b", email="b@test.com", roles=["learner"])

    # User A creates collection
    client.app.dependency_overrides[require_user] = lambda: user_a
    res_create = client.post("/me/collections", json={"name": "User A Collection"})
    assert res_create.status_code == 201
    coll_id = res_create.json()["id"]

    # User B lists collections -> empty
    client.app.dependency_overrides[require_user] = lambda: user_b
    res_b_list = client.get("/me/collections")
    assert res_b_list.status_code == 200
    assert res_b_list.json() == []

    # User B cannot access User A's collection
    assert client.get(f"/me/collections/{coll_id}").status_code == 404
    assert client.patch(f"/me/collections/{coll_id}", json={"expected_revision": 1, "name": "Hack"}).status_code == 404
    assert client.put(f"/me/collections/{coll_id}/scenes", json={"expected_revision": 1, "scene_ids": []}).status_code == 404
    # DELETE is idempotent: deleting nonexistent returns 204
    assert client.delete(f"/me/collections/{coll_id}").status_code == 204

    # User A still has their collection
    client.app.dependency_overrides[require_user] = lambda: user_a
    res_a_detail = client.get(f"/me/collections/{coll_id}")
    assert res_a_detail.status_code == 200
    assert res_a_detail.json()["name"] == "User A Collection"


def test_api_collections_unauthenticated(client: TestClient):
    client.app.dependency_overrides.clear()
    assert client.post("/me/collections", json={"name": "Test"}).status_code == 401
    assert client.get("/me/collections").status_code == 401
    assert client.get("/me/collections/col-01").status_code == 401
    assert client.patch("/me/collections/col-01", json={"expected_revision": 1, "name": "Test"}).status_code == 401
    assert client.put("/me/collections/col-01/scenes", json={"expected_revision": 1, "scene_ids": []}).status_code == 401
    assert client.delete("/me/collections/col-01").status_code == 401
