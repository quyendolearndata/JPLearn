"""Unit and contract tests for Content Versioning & Scenes (PR1 / ADR-007)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    ReturnToDraftCommand,
    SceneInput,
    UpdateContentDraftCommand,
)
from jplearn_api.application.handlers.content import (
    handle_get_published_content,
    handle_get_staff_content,
    handle_return_to_draft,
    handle_update_content_draft,
)
from jplearn_api.application.ports.repositories import ContentRepository
from jplearn_api.application.ports.unit_of_work import AsyncUnitOfWork
from jplearn_api.application.queries import GetPublishedContentQuery, GetStaffContentQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
)
from jplearn_api.entrypoints.http.app import create_app
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.security import require_user
from jplearn_api.settings import Settings


# ------------------------------------------------------------------------------
# In-Memory Test Doubles for Handlers
# ------------------------------------------------------------------------------

class InMemoryCatalogRepo:
    def __init__(self, items: dict[str, CatalogItem] | None = None) -> None:
        self.items = items or {}

    async def get_by_id(self, item_id: str) -> CatalogItem | None:
        return self.items.get(item_id)

    async def get_by_id_for_update(self, item_id: str) -> CatalogItem | None:
        return self.items.get(item_id)

    async def update(self, item: CatalogItem) -> None:
        self.items[item.id] = item


class InMemoryContentRepo:
    def __init__(self) -> None:
        self.versions: dict[str, list[ContentVersion]] = {}

    async def get_published_by_catalog_item_id(self, catalog_item_id: str) -> ContentVersion | None:
        versions = self.versions.get(catalog_item_id, [])
        for v in versions:
            if v.is_published:
                return v
        return None

    async def get_current_draft_by_catalog_item_id(self, catalog_item_id: str) -> ContentVersion | None:
        versions = self.versions.get(catalog_item_id, [])
        for v in versions:
            if not v.is_published:
                return v
        return None

    async def save_draft(self, content_version: ContentVersion) -> None:
        item_versions = self.versions.setdefault(content_version.catalog_item_id, [])
        for idx, v in enumerate(item_versions):
            if v.id == content_version.id:
                item_versions[idx] = content_version
                return
        item_versions.append(content_version)

    async def update(self, content_version: ContentVersion) -> None:
        await self.save_draft(content_version)

    async def get_max_version_number(self, catalog_item_id: str) -> int:
        versions = self.versions.get(catalog_item_id, [])
        if not versions:
            return 0
        return max((getattr(v, "version_number", 0) for v in versions), default=0)


class FakeUnitOfWork:
    def __init__(self, catalog_items: dict[str, CatalogItem] | None = None) -> None:
        self.catalog = InMemoryCatalogRepo(catalog_items)
        self.content = InMemoryContentRepo()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rolled_back = True
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


# ------------------------------------------------------------------------------
# Domain Tests
# ------------------------------------------------------------------------------

def test_scene_validation_timing():
    # Negative start time
    with pytest.raises(InvalidDomainStateError, match="start_time_seconds must be >= 0"):
        Scene("s1", 1, -1, 10, "Title", "Transcript")

    # End <= Start
    with pytest.raises(InvalidDomainStateError, match="end_time_seconds must be greater"):
        Scene("s1", 1, 10, 10, "Title", "Transcript")

    with pytest.raises(InvalidDomainStateError, match="end_time_seconds must be greater"):
        Scene("s1", 1, 15, 10, "Title", "Transcript")

    # Empty title or transcript
    with pytest.raises(InvalidDomainStateError, match="title_jp cannot be empty"):
        Scene("s1", 1, 0, 10, "   ", "Transcript")

    with pytest.raises(InvalidDomainStateError, match="transcript_jp cannot be empty"):
        Scene("s1", 1, 0, 10, "Title", "")


def test_content_version_cas_optimistic_lock():
    version = ContentVersion("v1", "item-1", revision=1)
    scenes = [
        Scene("s1", 1, 0, 10, "Scene 1", "こんにちは"),
        Scene("s2", 2, 10, 25, "Scene 2", "さようなら"),
    ]

    # Matching revision succeeds and increments revision to 2
    version.update_scenes(scenes, expected_revision=1, max_duration=30)
    assert version.revision == 2
    assert len(version.scenes) == 2

    # Stale revision fails with ConflictError
    with pytest.raises(ConflictError, match="Revision mismatch"):
        version.update_scenes(scenes, expected_revision=1, max_duration=30)


def test_content_version_scenes_exceeding_clip_duration():
    version = ContentVersion("v1", "item-1", revision=1)
    scenes = [Scene("s1", 1, 0, 45, "Scene 1", "Text")]
    with pytest.raises(InvalidDomainStateError, match="exceeds clip duration"):
        version.update_scenes(scenes, expected_revision=1, max_duration=30)


def test_content_version_non_contiguous_scene_index():
    version = ContentVersion("v1", "item-1", revision=1)
    scenes = [
        Scene("s1", 1, 0, 10, "Scene 1", "Text"),
        Scene("s3", 3, 10, 20, "Scene 3", "Text"),
    ]
    with pytest.raises(InvalidDomainStateError, match="Scene indices must be contiguous"):
        version.update_scenes(scenes, expected_revision=1)


# ------------------------------------------------------------------------------
# Application Handler Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_update_content_and_return_to_draft_flow():
    catalog_item = CatalogItem(
        id="item-01",
        topic_id="t1",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="high",
        title_internal="Lesson 1",
        created_by="user-staff",
        status="draft",
    )
    uow = FakeUnitOfWork({"item-01": catalog_item})

    # 1. Update draft scenes
    cmd = UpdateContentDraftCommand(
        catalog_item_id="item-01",
        version_revision=1,
        scenes=[
            SceneInput(1, 0, 20, "Intro", "皆さんこんにちは"),
            SceneInput(2, 20, 50, "Story", "昔々あるところに"),
        ],
    )
    dto = await handle_update_content_draft(cmd, uow)
    assert dto.revision == 2
    assert len(dto.scenes) == 2
    assert dto.scenes[0].title_jp == "Intro"

    # 2. Submit for QA
    catalog_item.submit_for_qa()
    assert catalog_item.status == "level_qa"
    draft_v = await uow.content.get_current_draft_by_catalog_item_id("item-01")
    draft_v.freeze_for_qa()
    assert draft_v.is_frozen is True

    # 3. Cannot modify scenes when frozen
    with pytest.raises(InvalidDomainStateError):
        await handle_update_content_draft(cmd, uow)

    # 4. Return to draft
    return_cmd = ReturnToDraftCommand(catalog_item_id="item-01")
    updated_item_dto = await handle_return_to_draft(return_cmd, uow)
    assert updated_item_dto.status == "draft"
    assert draft_v.is_frozen is False

    # 5. Now update succeeds with new revision
    cmd2 = UpdateContentDraftCommand(
        catalog_item_id="item-01",
        version_revision=2,
        scenes=[
            SceneInput(1, 0, 25, "Intro Revised", "皆さんこんにちは、今日もお元気ですか"),
        ],
    )
    dto2 = await handle_update_content_draft(cmd2, uow)
    assert dto2.revision == 3
    assert len(dto2.scenes) == 1


# ------------------------------------------------------------------------------
# HTTP API Integration / Security Tests
# ------------------------------------------------------------------------------

from jplearn_api.entrypoints.http.dependencies import get_session


def test_http_get_content_unauthenticated_returns_401(client: TestClient):
    res = client.get("/catalog/00000000-0000-4000-8000-0000000000aa/content")
    assert res.status_code == 401
    assert res.json()["statusCode"] == 401


def test_http_staff_content_forbidden_for_learner(client: TestClient):
    learner = UserDTO(id="u1", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner
    try:
        res_get = client.get("/staff/catalog/00000000-0000-4000-8000-0000000000aa/content")
        assert res_get.status_code == 403
        assert res_get.json()["statusCode"] == 403

        res_put = client.put(
            "/staff/catalog/00000000-0000-4000-8000-0000000000aa/content",
            json={"version_revision": 1, "scenes": []},
        )
        assert res_put.status_code == 403

        res_return = client.post("/staff/catalog/00000000-0000-4000-8000-0000000000aa/return-to-draft")
        assert res_return.status_code == 403
    finally:
        client.app.dependency_overrides.pop(require_user, None)


def test_http_put_content_validation_errors(client: TestClient):
    from jplearn_api.entrypoints.http.dependencies import require_capability

    teacher = UserDTO(id="u2", email="teacher@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: teacher
    client.app.dependency_overrides[require_roles("teacher", "admin")] = lambda: teacher
    client.app.dependency_overrides[require_capability("video_scene_breakdown_enabled")] = lambda: None
    try:
        # Empty payload
        res = client.put("/staff/catalog/00000000-0000-4000-8000-0000000000aa/content", json={})
        assert res.status_code == 400
        assert res.json()["statusCode"] == 400
    finally:
        client.app.dependency_overrides.pop(require_user, None)
        client.app.dependency_overrides.pop(require_roles("teacher", "admin"), None)
        client.app.dependency_overrides.pop(require_capability("video_scene_breakdown_enabled"), None)


# ------------------------------------------------------------------------------
# R2 Remediation Tests (P1.2, P1.8, P2)
# ------------------------------------------------------------------------------

def test_scene_overlap_prevention():
    """R2: Overlapping scenes must be rejected by domain validation."""
    version = ContentVersion("v1", "item-1", revision=1)
    scenes = [
        Scene("s1", 1, 0, 20, "Scene 1", "こんにちは"),
        Scene("s2", 2, 15, 35, "Scene 2", "重なっています"),
    ]
    with pytest.raises(InvalidDomainStateError, match="Scenes must not overlap"):
        version.update_scenes(scenes, expected_revision=1, max_duration=60)


@pytest.mark.asyncio
async def test_incremental_version_numbering_lifecycle():
    """R2 (P1.2): Version numbering increments monotonically on subsequent drafts after publish."""
    catalog_item = CatalogItem(
        id="item-02",
        topic_id="t1",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="high",
        title_internal="Lesson 2",
        created_by="user-staff",
        status="draft",
    )
    uow = FakeUnitOfWork({"item-02": catalog_item})

    # 1. Draft 1
    v1_dto = await handle_update_content_draft(
        UpdateContentDraftCommand(
            catalog_item_id="item-02",
            version_revision=1,
            scenes=[SceneInput(1, 0, 30, "Scene 1", "こんにちは")],
        ),
        uow,
    )
    assert v1_dto.version_number == 1
    assert v1_dto.revision == 2

    # 2. Publish version 1
    v1 = await uow.content.get_current_draft_by_catalog_item_id("item-02")
    from datetime import datetime, timezone
    v1.publish(datetime.now(timezone.utc))
    await uow.content.update(v1)

    # 3. GET staff content does NOT create a draft row, but projects next version number
    staff_view = await handle_get_staff_content(
        GetStaffContentQuery(catalog_item_id="item-02"),
        uow,
    )
    assert staff_view.version_number == 2
    assert staff_view.id == ""  # Transient DTO
    # Ensure no new draft row was silently persisted in DB
    draft_in_db = await uow.content.get_current_draft_by_catalog_item_id("item-02")
    assert draft_in_db is None

    # 4. PUT content creates Draft 2 with version_number = 2
    v2_dto = await handle_update_content_draft(
        UpdateContentDraftCommand(
            catalog_item_id="item-02",
            version_revision=1,
            scenes=[SceneInput(1, 0, 40, "Scene 1 v2", "こんにちは改訂版")],
        ),
        uow,
    )
    assert v2_dto.version_number == 2
    assert v2_dto.revision == 2
    assert v2_dto.scenes[0].title_jp == "Scene 1 v2"


@pytest.mark.asyncio
async def test_media_upload_blocked_when_item_not_draft():
    """R2 (P1.8): Media upload must be rejected when catalog item is in level_qa or published."""
    from fakes import FakeMediaRepository, FakeMediaUrlSigner, FakeStoragePort, create_fake_uow_factory
    from jplearn_api.application.handlers.media import handle_upload_media

    media_repo = FakeMediaRepository()
    media_repo.catalog_items.add("cat-item-qa")
    media_repo.catalog_item_statuses = {"cat-item-qa": "level_qa"}
    storage = FakeStoragePort()
    signer = FakeMediaUrlSigner()

    valid_first_chunk = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"

    async def fake_stream():
        yield b"chunk-data"

    with pytest.raises(InvalidDomainStateError, match="must be in 'draft' status"):
        await handle_upload_media(
            catalog_item_id="cat-item-qa",
            first_chunk=valid_first_chunk,
            stream=fake_stream(),
            filename="video.mp4",
            content_type="video/mp4",
            uow_factory=create_fake_uow_factory(media=media_repo),
            storage=storage,
            signer=signer,
        )
