"""Unit, handler, and contract tests for Content Reports and Moderation (PR3b / ADR-007 / UC-L24 / UC-T09 / FR-RPT-001)."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    CreateContentReportCommand,
    PatchStaffContentReportCommand,
)
from jplearn_api.application.handlers.content_reports import (
    handle_create_report,
    handle_get_my_report,
    handle_get_staff_report,
    handle_list_my_reports,
    handle_list_staff_reports,
    handle_patch_staff_report,
)
from jplearn_api.application.queries import (
    GetMyContentReportQuery,
    GetStaffContentReportQuery,
    ListMyContentReportsQuery,
    ListStaffContentReportsQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.content_report import (
    ContentReport,
    ReportCategory,
    ReportStatus,
)
from jplearn_api.domain.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidDomainStateError,
    QuotaExceededError,
    RevisionConflictError,
)
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.security import require_user
from fakes import (
    FakeCatalogRepository,
    FakeContentReportRepository,
    FakeContentRepository,
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
    client.app.state.settings.content_reports_enabled = True
    yield
    client.app.state.settings.content_reports_enabled = False


@pytest.fixture
def report_test_env():
    now = datetime.now(timezone.utc)
    item_pub = CatalogItem(
        id="item-01",
        topic_id="topic-01",
        ci_level=1,
        duration_seconds=120,
        media_type="video",
        visual_support="high",
        title_internal="Published Video",
        status="published",
        created_by="teacher-01",
    )
    item_draft = CatalogItem(
        id="item-draft",
        topic_id="topic-01",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="high",
        title_internal="Draft Video",
        status="draft",
        created_by="teacher-01",
    )

    ver_pub = ContentVersion(
        id="ver-01",
        catalog_item_id="item-01",
        version_number=1,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=[
            Scene(
                id="sc-01",
                scene_index=0,
                start_time_seconds=0,
                end_time_seconds=10,
                title_jp="挨拶",
                transcript_jp="おはようございます",
            ),
            Scene(
                id="sc-02",
                scene_index=1,
                start_time_seconds=10,
                end_time_seconds=25,
                title_jp="自己紹介",
                transcript_jp="私は田中です",
            ),
        ],
    )

    ver_draft = ContentVersion(
        id="ver-draft",
        catalog_item_id="item-01",
        version_number=2,
        revision=1,
        is_frozen=False,
        is_published=False,
        scenes=[
            Scene(
                id="sc-draft-01",
                scene_index=0,
                start_time_seconds=0,
                end_time_seconds=15,
                title_jp="下書き",
                transcript_jp="テスト",
            )
        ],
    )

    ver_res = ContentVersion(
        id="ver-res",
        catalog_item_id="item-01",
        version_number=3,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=[
            Scene(
                id="sc-res-01",
                scene_index=0,
                start_time_seconds=0,
                end_time_seconds=12,
                title_jp="挨拶修正",
                transcript_jp="おはようございます！",
            )
        ],
    )

    cat_repo = FakeCatalogRepository()
    _add_catalog_item(cat_repo, item_pub)
    _add_catalog_item(cat_repo, item_draft)

    cnt_repo = FakeContentRepository()
    _add_version(cnt_repo, ver_pub)
    _add_version(cnt_repo, ver_draft)
    _add_version(cnt_repo, ver_res)

    rpt_repo = FakeContentReportRepository()

    uow = FakeUnitOfWork(
        catalog=cat_repo,
        content=cnt_repo,
        content_reports=rpt_repo,
    )

    return {
        "uow": uow,
        "cat_repo": cat_repo,
        "cnt_repo": cnt_repo,
        "rpt_repo": rpt_repo,
    }


# ------------------------------------------------------------------------------
# 1. Domain / Handler Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_report_success(report_test_env):
    uow = report_test_env["uow"]
    cmd = CreateContentReportCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        content_version_id="ver-01",
        scene_id="sc-01",
        position_ms=5000,
        category="audio_quality",
        description="Audio is too quiet here",
    )
    report = await handle_create_report(cmd, uow)
    assert report.id.startswith("rpt_")
    assert report.user_id == "user-01"
    assert report.catalog_item_id == "item-01"
    assert report.content_version_id == "ver-01"
    assert report.scene_id == "sc-01"
    assert report.position_ms == 5000
    assert report.category == ReportCategory.AUDIO_QUALITY
    assert report.description == "Audio is too quiet here"
    assert report.status == ReportStatus.OPEN
    assert report.revision == 1
    assert report.public_reply is None
    assert report.internal_note is None


@pytest.mark.asyncio
async def test_create_report_without_scene_id_success(report_test_env):
    uow = report_test_env["uow"]
    cmd = CreateContentReportCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        content_version_id="ver-01",
        scene_id=None,
        position_ms=15000,
        category="scene_timing",
        description="Timing gap observed",
    )
    report = await handle_create_report(cmd, uow)
    assert report.scene_id is None
    assert report.position_ms == 15000
    assert report.category == ReportCategory.SCENE_TIMING


@pytest.mark.asyncio
async def test_create_report_validations(report_test_env):
    uow = report_test_env["uow"]

    # 1. Empty description
    with pytest.raises(InvalidDomainStateError, match="Description must be between 1 and 1000 characters"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                category="other",
                description="   ",
            ),
            uow,
        )

    # 2. Too long description (> 1000 chars)
    with pytest.raises(InvalidDomainStateError, match="Description must be between 1 and 1000 characters"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                category="other",
                description="x" * 1001,
            ),
            uow,
        )

    # 3. Invalid category
    with pytest.raises(InvalidDomainStateError, match="Invalid report category"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                category="not_a_category",
                description="test",
            ),
            uow,
        )

    # 4. Unpublished catalog item
    with pytest.raises(InvalidDomainStateError, match="Reports can only be submitted for published catalog items"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-draft",
                content_version_id="ver-01",
                category="other",
                description="Draft item report",
            ),
            uow,
        )

    # 5. Unpublished content version
    with pytest.raises(InvalidDomainStateError, match="Reports can only be filed on currently published version"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-01",
                content_version_id="ver-draft",
                category="other",
                description="Draft version report",
            ),
            uow,
        )

    # 6. Position out of bounds (> 120s = 120000ms)
    with pytest.raises(InvalidDomainStateError, match="out of bounds"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                position_ms=130000,
                category="other",
                description="Out of bounds",
            ),
            uow,
        )

    # 7. Scene does not belong to version
    with pytest.raises(InvalidDomainStateError, match="Scene does not belong to specified content version"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-01",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                scene_id="sc-draft-01",
                category="other",
                description="Wrong scene",
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_create_report_idempotency(report_test_env):
    uow = report_test_env["uow"]
    cmd = CreateContentReportCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        content_version_id="ver-01",
        scene_id="sc-01",
        position_ms=5000,
        category="audio_quality",
        description="Idempotent test",
        idempotency_key="idem-key-123",
    )
    r1 = await handle_create_report(cmd, uow)
    r2 = await handle_create_report(cmd, uow)
    assert r1.id == r2.id

    # Same idempotency key with different payload must raise ConflictError
    cmd_conflict = CreateContentReportCommand(
        user_id="user-01",
        catalog_item_id="item-01",
        content_version_id="ver-01",
        scene_id="sc-01",
        position_ms=6000,
        category="audio_quality",
        description="Different payload",
        idempotency_key="idem-key-123",
    )
    with pytest.raises(ConflictError, match="Idempotency key reused with different request payload"):
        await handle_create_report(cmd_conflict, uow)


@pytest.mark.asyncio
async def test_daily_report_quota_limit_10(report_test_env):
    uow = report_test_env["uow"]

    # Submit 10 reports -> all succeed
    for i in range(10):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-quota",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                category="other",
                description=f"Report number {i}",
            ),
            uow,
        )

    # 11th report -> QuotaExceededError
    with pytest.raises(QuotaExceededError, match="Daily report limit of 10 reached"):
        await handle_create_report(
            CreateContentReportCommand(
                user_id="user-quota",
                catalog_item_id="item-01",
                content_version_id="ver-01",
                category="other",
                description="Report number 11",
            ),
            uow,
        )


@pytest.mark.asyncio
async def test_staff_moderation_workflow_and_occ(report_test_env):
    uow = report_test_env["uow"]

    # 1. Learner creates report
    report = await handle_create_report(
        CreateContentReportCommand(
            user_id="learner-01",
            catalog_item_id="item-01",
            content_version_id="ver-01",
            category="visual_mismatch",
            description="Subtitle does not match actor speech",
        ),
        uow,
    )
    assert report.status == ReportStatus.OPEN
    assert report.revision == 1

    # 2. Staff views moderation queue
    reports, total = await handle_list_staff_reports(ListStaffContentReportsQuery(), uow)
    assert total == 1
    assert reports[0].id == report.id

    # 3. Staff patches with mismatched revision -> RevisionConflictError
    with pytest.raises(RevisionConflictError, match="Expected revision 99"):
        await handle_patch_staff_report(
            PatchStaffContentReportCommand(
                report_id=report.id,
                expected_revision=99,
                actor_id="teacher-01",
                status="in_review",
            ),
            uow,
        )

    # 4. Staff patches with matching revision -> advances to in_review
    p1 = await handle_patch_staff_report(
        PatchStaffContentReportCommand(
            report_id=report.id,
            expected_revision=1,
            actor_id="teacher-01",
            status="in_review",
            assignee_id="teacher-01",
            internal_note="Investigating with audio editor",
            reason="Triage into in_review",
        ),
        uow,
    )
    assert p1.status == ReportStatus.IN_REVIEW
    assert p1.revision == 2
    assert p1.internal_note == "Investigating with audio editor"

    # 5. Check staff detail includes audit record
    detail, audits = await handle_get_staff_report(GetStaffContentReportQuery(report_id=report.id), uow)
    assert detail.revision == 2
    assert len(audits) == 1
    assert audits[0].from_status == ReportStatus.OPEN
    assert audits[0].to_status == ReportStatus.IN_REVIEW
    assert audits[0].revision == 2
    assert audits[0].reason == "Triage into in_review"

    # 6. Reject invalid resolution version
    with pytest.raises(InvalidDomainStateError, match="Resolution version must be published"):
        await handle_patch_staff_report(
            PatchStaffContentReportCommand(
                report_id=report.id,
                expected_revision=2,
                actor_id="teacher-01",
                status="resolved",
                resolution_version_id="ver-draft",  # draft, not published
            ),
            uow,
        )

    # 7. Resolve with valid published version
    resolved = await handle_patch_staff_report(
        PatchStaffContentReportCommand(
            report_id=report.id,
            expected_revision=2,
            actor_id="teacher-01",
            status="resolved",
            public_reply="Corrected subtitles in version 3",
            internal_note="Fixed in release v3",
            resolution_version_id="ver-res",
            reason="Resolved with v3 publish",
        ),
        uow,
    )
    assert resolved.status == ReportStatus.RESOLVED
    assert resolved.revision == 3
    assert resolved.public_reply == "Corrected subtitles in version 3"
    assert resolved.resolution_version_id == "ver-res"


# ------------------------------------------------------------------------------
# 2. HTTP API Contract & Privacy Tests
# ------------------------------------------------------------------------------

def test_api_learner_report_lifecycle_and_privacy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, report_test_env
):
    uow = report_test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.content_reports.create_uow", lambda session: uow)

    learner = UserDTO(id="user-learner", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    # 1. POST /catalog/item-01/reports -> 201 Created
    res_post = client.post(
        "/catalog/item-01/reports",
        json={
            "content_version_id": "ver-01",
            "scene_id": "sc-01",
            "position_ms": 2000,
            "category": "audio_quality",
            "description": "Sound distorts here",
        },
    )
    assert res_post.status_code == 201, res_post.text
    data = res_post.json()
    report_id = data["id"]
    assert data["category"] == "audio_quality"
    assert data["status"] == "open"
    assert data["position_ms"] == 2000

    # PRIVACY CRITICAL INVARIANT: Learner schema must never expose internal_note or assignee_id!
    assert "internal_note" not in data
    assert "assignee_id" not in data

    # 2. GET /me/content-reports
    res_list = client.get("/me/content-reports")
    assert res_list.status_code == 200
    assert res_list.headers.get("X-Total-Count") == "1"
    items = res_list.json()
    assert len(items) == 1
    assert items[0]["id"] == report_id
    assert "internal_note" not in items[0]
    assert "assignee_id" not in items[0]

    # 3. GET /me/content-reports/{id}
    res_get = client.get(f"/me/content-reports/{report_id}")
    assert res_get.status_code == 200
    item = res_get.json()
    assert item["id"] == report_id
    assert "internal_note" not in item
    assert "assignee_id" not in item

    # 4. Data isolation: User B cannot access User A's report
    user_b = UserDTO(id="user-b", email="b@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: user_b
    res_other = client.get(f"/me/content-reports/{report_id}")
    assert res_other.status_code == 404

    res_list_b = client.get("/me/content-reports")
    assert res_list_b.status_code == 200
    assert len(res_list_b.json()) == 0


def test_api_staff_moderation_full_flow(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, report_test_env
):
    uow = report_test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.content_reports.create_uow", lambda session: uow)

    # 1. Create a report as learner
    learner = UserDTO(id="learner-42", email="learner42@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    res_post = client.post(
        "/catalog/item-01/reports",
        json={
            "content_version_id": "ver-01",
            "category": "visual_mismatch",
            "description": "Wrong kanji subtitle",
            "position_ms": 3000,
        },
    )
    assert res_post.status_code == 201
    report_id = res_post.json()["id"]

    # 2. Learner tries calling staff endpoint -> 403 Forbidden
    res_forbidden = client.get("/staff/content-reports")
    assert res_forbidden.status_code == 403

    # 3. Switch to Staff user
    staff = UserDTO(id="staff-01", email="staff@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: staff

    res_staff_list = client.get("/staff/content-reports")
    assert res_staff_list.status_code == 200
    assert res_staff_list.headers.get("X-Total-Count") == "1"
    staff_items = res_staff_list.json()
    assert len(staff_items) == 1
    report_data = staff_items[0]
    assert report_data["id"] == report_id
    assert report_data["revision"] == 1
    assert "internal_note" in report_data

    # 4. Patch with conflicting revision -> 409 Conflict
    res_conflict = client.patch(
        f"/staff/content-reports/{report_id}",
        json={
            "expected_revision": 10,
            "status": "in_review",
        },
    )
    assert res_conflict.status_code == 409

    # 5. Patch with valid expected_revision -> 200 OK
    res_patch = client.patch(
        f"/staff/content-reports/{report_id}",
        json={
            "expected_revision": 1,
            "status": "in_review",
            "assignee_id": "staff-01",
            "internal_note": "Assigned to linguist team",
            "reason": "Triage start",
        },
    )
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["status"] == "in_review"
    assert patched["revision"] == 2
    assert patched["assignee_id"] == "staff-01"
    assert patched["internal_note"] == "Assigned to linguist team"

    # 6. Staff gets detail with audit logs
    res_detail = client.get(f"/staff/content-reports/{report_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["revision"] == 2
    assert len(detail["audit_logs"]) == 1
    assert detail["audit_logs"][0]["from_status"] == "open"
    assert detail["audit_logs"][0]["to_status"] == "in_review"
    assert detail["audit_logs"][0]["actor_id"] == "staff-01"

    # 7. Staff resolves report with public_reply and resolution_version_id
    res_resolve = client.patch(
        f"/staff/content-reports/{report_id}",
        json={
            "expected_revision": 2,
            "status": "resolved",
            "public_reply": "Thank you! Fixed in our latest content update.",
            "internal_note": "Re-verified and approved by QA",
            "resolution_version_id": "ver-res",
            "reason": "Resolved via v3 publish",
        },
    )
    assert res_resolve.status_code == 200
    resolved_data = res_resolve.json()
    assert resolved_data["status"] == "resolved"
    assert resolved_data["revision"] == 3
    assert resolved_data["resolution_version_id"] == "ver-res"

    # 8. Learner checks status: sees resolution and public_reply, NEVER internal_note
    client.app.dependency_overrides[require_user] = lambda: learner
    res_learner_check = client.get(f"/me/content-reports/{report_id}")
    assert res_learner_check.status_code == 200
    learner_data = res_learner_check.json()
    assert learner_data["status"] == "resolved"
    assert learner_data["public_reply"] == "Thank you! Fixed in our latest content update."
    assert learner_data["resolution_version_id"] == "ver-res"
    assert "internal_note" not in learner_data
    assert "assignee_id" not in learner_data


def test_api_daily_quota_429(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, report_test_env
):
    uow = report_test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.content_reports.create_uow", lambda session: uow)

    spammer = UserDTO(id="spammer-01", email="spammer@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: spammer

    # 10 successful reports
    for i in range(10):
        r = client.post(
            "/catalog/item-01/reports",
            json={
                "content_version_id": "ver-01",
                "category": "other",
                "description": f"Spam attempt {i}",
            },
        )
        assert r.status_code == 201, f"Failed on report {i}: {r.text}"

    # 11th report -> 429 Too Many Requests
    r_limit = client.post(
        "/catalog/item-01/reports",
        json={
            "content_version_id": "ver-01",
            "category": "other",
            "description": "Spam attempt 11",
        },
    )
    assert r_limit.status_code == 429
    assert "Daily report limit of 10 reached" in r_limit.text
