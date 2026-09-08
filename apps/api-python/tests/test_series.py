"""Unit, handler, and contract tests for Series & Episodes (PR2 / ADR-007)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fakes import FakeCatalogRepository, FakeSeriesRepository, FakeUnitOfWork
from jplearn_api.application.handlers.series import (
    handle_create_series,
    handle_get_learner_series,
    handle_list_learner_series,
    handle_publish_series,
    handle_return_series_to_draft,
    handle_submit_series_qa,
    handle_update_series_items,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    InvalidDomainStateError,
    RevisionConflictError,
)
from jplearn_api.domain.series import Series, SeriesItem
from jplearn_api.entrypoints.http.security import require_user

# ------------------------------------------------------------------------------
# Domain Tests
# ------------------------------------------------------------------------------


def test_series_domain_creation_and_defaults():
    series = Series(
        id="series-01",
        title="Living in Tokyo",
        description="Daily life immersion",
        ci_level="1",
        topic_id="topic-daily",
    )
    assert series.status == "draft"
    assert series.revision == 1
    assert series.items == []


def test_series_domain_metadata_update_cas():
    series = Series("series-01", "Tokyo", "Desc", "1", "topic-1", revision=1)
    series.update_metadata(expected_revision=1, title="Living in Tokyo Updated", ci_level="2")
    assert series.title == "Living in Tokyo Updated"
    assert series.ci_level == "2"
    assert series.revision == 2

    # Stale revision conflict
    with pytest.raises(RevisionConflictError):
        series.update_metadata(expected_revision=1, title="Stale")


def test_series_domain_update_items_ordering_and_duplicates():
    series = Series("series-01", "Tokyo", "Desc", "1", "topic-1", revision=1)

    # Duplicate IDs rejected
    with pytest.raises(InvalidDomainStateError, match="Duplicate"):
        series.update_items(expected_revision=1, catalog_item_ids=["item-1", "item-1"])

    # Valid items updated with 1-based sequential positions
    series.update_items(expected_revision=1, catalog_item_ids=["item-1", "item-2", "item-3"])
    assert series.revision == 2
    assert len(series.items) == 3
    assert series.items[0].catalog_item_id == "item-1"
    assert series.items[0].position == 1
    assert series.items[1].catalog_item_id == "item-2"
    assert series.items[1].position == 2
    assert series.items[2].catalog_item_id == "item-3"
    assert series.items[2].position == 3


def test_series_domain_qa_and_publish_invariants():
    series = Series("series-01", "Tokyo", "Desc", "1", "topic-1", revision=1)

    # Cannot submit for QA without items
    with pytest.raises(InvalidDomainStateError, match="at least one item"):
        series.submit_qa(expected_revision=1)

    series.update_items(expected_revision=1, catalog_item_ids=["clip-01", "clip-02"])
    assert series.revision == 2

    # Submit QA
    series.submit_qa(expected_revision=2)
    assert series.status == "level_qa"
    assert series.revision == 3

    # Publish rejected if any constituent clip is not published
    with pytest.raises(InvalidDomainStateError, match="are not published"):
        series.publish(expected_revision=3, published_catalog_ids={"clip-01"})  # clip-02 missing

    # Publish succeeds when all constituent clips are published
    series.publish(expected_revision=3, published_catalog_ids={"clip-01", "clip-02"})
    assert series.status == "published"
    assert series.revision == 4

    # Unpublish
    series.unpublish(expected_revision=4)
    assert series.status == "unpublished"
    assert series.revision == 5


# ------------------------------------------------------------------------------
# Application Handler Tests
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_series_lifecycle():
    clip_1 = CatalogItem(
        id="clip-01",
        topic_id="topic-1",
        ci_level=1,
        duration_seconds=30,
        media_type="video",
        visual_support="high",
        title_internal="Clip 1",
        created_by="staff",
        status="published",
    )
    clip_2 = CatalogItem(
        id="clip-02",
        topic_id="topic-1",
        ci_level=1,
        duration_seconds=45,
        media_type="video",
        visual_support="high",
        title_internal="Clip 2",
        created_by="staff",
        status="published",
    )

    catalog_repo = FakeCatalogRepository({"clip-01": clip_1, "clip-02": clip_2})
    uow = FakeUnitOfWork(catalog=catalog_repo)

    # 1. Create series
    series = await handle_create_series(
        uow=uow,
        title="Series A",
        description="First immersion series",
        ci_level="1",
        topic_id="topic-1",
    )
    assert series.status == "draft"
    assert series.revision == 1

    # 2. Add constituent items
    series = await handle_update_series_items(
        uow=uow,
        series_id=series.id,
        expected_revision=1,
        item_ids=["clip-01", "clip-02"],
    )
    assert series.revision == 2

    # 3. Submit QA
    series = await handle_submit_series_qa(
        uow=uow,
        series_id=series.id,
        expected_revision=2,
    )
    assert series.status == "level_qa"

    # 4. Return to draft by admin
    series = await handle_return_series_to_draft(
        uow=uow,
        series_id=series.id,
        expected_revision=3,
        reason="Need order tweak",
    )
    assert series.status == "draft"

    # 5. Submit QA again and Publish
    series = await handle_submit_series_qa(uow, series.id, expected_revision=4)
    series = await handle_publish_series(uow, series.id, expected_revision=5)
    assert series.status == "published"

    # 6. Learner lists series
    learner_series_list = await handle_list_learner_series(uow)
    assert len(learner_series_list) == 1
    found_series, available_count = learner_series_list[0]
    assert found_series.id == series.id
    assert available_count == 2

    # 7. Learner gets series detail
    found_series, clips = await handle_get_learner_series(uow, series.id)
    assert found_series.id == series.id
    assert len(clips) == 2
    assert clips[0]["catalog_item_id"] == "clip-01"
    assert clips[1]["catalog_item_id"] == "clip-02"


@pytest.mark.asyncio
async def test_handler_learner_series_when_clips_unpublished():
    clip_1 = CatalogItem("clip-01", "topic-1", 1, 30, "video", "high", "Clip 1", "staff", status="published")
    clip_2 = CatalogItem("clip-02", "topic-1", 1, 45, "video", "high", "Clip 2", "staff", status="published")

    catalog_repo = FakeCatalogRepository({"clip-01": clip_1, "clip-02": clip_2})
    uow = FakeUnitOfWork(catalog=catalog_repo)

    series = await handle_create_series(uow, "Series B", "Desc", "1", "topic-1")
    series = await handle_update_series_items(uow, series.id, 1, ["clip-01", "clip-02"])
    series = await handle_submit_series_qa(uow, series.id, 2)
    series = await handle_publish_series(uow, series.id, 3)

    # Simulate: clip_2 is unpublished
    catalog_repo._committed_items["clip-02"].status = "draft"
    catalog_repo.items["clip-02"].status = "draft"

    # Learner should still see the series, but available_item_count is now 1
    learner_list = await handle_list_learner_series(uow)
    assert len(learner_list) == 1
    _, available_count = learner_list[0]
    assert available_count == 1

    # Detail only returns clip-01
    _, clips = await handle_get_learner_series(uow, series.id)
    assert len(clips) == 1
    assert clips[0]["catalog_item_id"] == "clip-01"

    # Simulate: clip_1 also unpublished -> 0 available clips
    catalog_repo._committed_items["clip-01"].status = "draft"
    catalog_repo.items["clip-01"].status = "draft"
    learner_list = await handle_list_learner_series(uow)
    assert len(learner_list) == 0  # Series hidden from learner list

    # Detail returns 404 (EntityNotFoundError)
    with pytest.raises(EntityNotFoundError, match="has no available items"):
        await handle_get_learner_series(uow, series.id)


# ------------------------------------------------------------------------------
# API Integration & Contract Tests
# ------------------------------------------------------------------------------


def test_api_staff_series_crud_and_permissions(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    clip_1 = CatalogItem("clip-01", "topic-1", 1, 30, "video", "high", "Clip 1", "staff", status="published")
    catalog_repo = FakeCatalogRepository({"clip-01": clip_1})
    uow = FakeUnitOfWork(catalog=catalog_repo)
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.series.create_uow", lambda session: uow)

    app = client.app
    teacher = UserDTO(id="teacher-uuid-01", email="teacher@jplearn.local", roles=["teacher"])
    learner = UserDTO(id="learner-uuid-01", email="learner@jplearn.local", roles=["learner"])

    # 1. Learner cannot POST /staff/series
    app.dependency_overrides[require_user] = lambda: learner
    resp = client.post("/staff/series", json={"title": "Test", "ci_level": "1", "topic_id": "topic-1"})
    assert resp.status_code == 403

    # 2. Teacher can create series
    app.dependency_overrides[require_user] = lambda: teacher
    resp = client.post(
        "/staff/series",
        json={"title": "Natural Situations", "description": "Conversations", "ci_level": "1", "topic_id": "topic-1"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Natural Situations"
    assert data["status"] == "draft"
    assert data["revision"] == 1
    series_id = data["id"]

    # 3. Teacher can list staff series
    resp = client.get("/staff/series")
    assert resp.status_code == 200
    series_list = resp.json()
    assert any(s["id"] == series_id for s in series_list)

    # 4. Teacher can PATCH metadata with revision check
    resp = client.patch(f"/staff/series/{series_id}", json={"expected_revision": 1, "title": "Situations in Kyoto"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Situations in Kyoto"
    assert resp.json()["revision"] == 2

    # Stale revision returns 409
    resp = client.patch(f"/staff/series/{series_id}", json={"expected_revision": 1, "title": "Stale Attempt"})
    assert resp.status_code == 409

    # Clean up overrides
    app.dependency_overrides.clear()


def test_api_learner_series_view_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    clip_1 = CatalogItem("clip-01", "topic-1", 1, 30, "video", "high", "Clip 1", "staff", status="published")
    catalog_repo = FakeCatalogRepository({"clip-01": clip_1})
    series = Series(
        id="00000000-0000-4000-8000-0000000000bb",
        title="Tokyo Life",
        description="Daily life",
        ci_level="1",
        topic_id="topic-1",
        status="published",
        revision=2,
        items=[SeriesItem(catalog_item_id="clip-01", position=1)],
    )
    series_repo = FakeSeriesRepository([series])
    uow = FakeUnitOfWork(catalog=catalog_repo, series=series_repo)
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.series.create_uow", lambda session: uow)

    app = client.app
    learner = UserDTO(id="learner-uuid-01", email="learner@jplearn.local", roles=["learner"])

    # 1. Without auth, GET /series is 401
    resp = client.get("/series")
    assert resp.status_code == 401

    # 2. With auth, GET /series is 200
    app.dependency_overrides[require_user] = lambda: learner
    resp = client.get("/series")
    assert resp.status_code == 200
    series_list = resp.json()
    assert len(series_list) == 1
    assert series_list[0]["id"] == series.id
    assert series_list[0]["available_item_count"] == 1

    # 3. GET /series/{id} returns clips without L1 fields
    resp_detail = client.get(f"/series/{series.id}")
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["id"] == series.id
    assert len(detail["items"]) == 1
    clip_data = detail["items"][0]
    assert clip_data["catalog_item_id"] == "clip-01"
    assert "translation_vi" not in clip_data
    assert "grammar" not in clip_data
    assert "vocabulary" not in clip_data

    app.dependency_overrides.clear()
