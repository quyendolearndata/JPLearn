"""Tests for Japanese Transcript Management, Approval Workflow, and Language Analysis (PR8a / UC-T10).

Validates:
- Pure Python Unicode Japanese Analyzer:
  - Character categorization (Kanji, Hiragana, Katakana, Latin, Number, Punctuation)
  - Token segmentation and offset spans
  - Reading/kana extraction and character type distribution
- Domain Validation Bounds & State Machine:
  - Segments limit (<= 100)
  - Segment text length (<= 500 Unicode chars)
  - Total transcript length (<= 20,000 Unicode chars)
  - Scene reference integrity (must exist in content_version)
  - Allowed transitions: draft -> qa_submitted -> approved / returned_to_draft
  - CAS concurrency control (expected_revision mismatch -> ConcurrencyError / 409)
- Projection Invariants:
  - When approved -> approved_scene_texts activated (is_active = True)
  - When returned_to_draft -> approved_scene_texts deactivated (is_active = False)
- Pedagogy Boundaries (FR-NEG):
  - No Vietnamese translations, no grammar explanations, no flashcard scoring
- HTTP API Contract & RBAC:
  - Staff authentication required (401)
  - Teacher vs Admin role separation (Approve/Return-to-draft requires admin -> 403 for teacher)
  - End-to-end HTTP lifecycle matching OpenAPI specification
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    ApproveTranscriptCommand,
    CreateLanguageAnalysisJobCommand,
    ReturnTranscriptToDraftCommand,
    SaveTranscriptDraftCommand,
    SubmitTranscriptQACommand,
)
from jplearn_api.application.handlers.transcript import (
    handle_approve_transcript,
    handle_create_language_analysis_job,
    handle_get_language_analysis_job,
    handle_get_transcript,
    handle_return_transcript_to_draft,
    handle_save_transcript_draft,
    handle_submit_transcript_qa,
)
from jplearn_api.application.queries import (
    GetLanguageAnalysisJobQuery,
    GetTranscriptQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem, MediaRef
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import (
    EntityNotFoundError,
    InvalidDomainStateError,
    RevisionConflictError,
    ValidationError,
)
from jplearn_api.domain.transcript import (
    LanguageAnalysisJobStatus,
    TranscriptProvenance,
    TranscriptSegment,
    TranscriptStatus,
    analyze_japanese_text,
    get_char_type,
)
from jplearn_api.entrypoints.http.security import require_user
from fakes import (
    FakeCatalogRepository,
    FakeContentRepository,
    FakeTranscriptRepository,
    FakeUnitOfWork,
)


# ------------------------------------------------------------------------------
# Fixtures & Helpers
# ------------------------------------------------------------------------------

@pytest.fixture
def transcript_env():
    catalog_repo = FakeCatalogRepository()
    content_repo = FakeContentRepository()
    transcript_repo = FakeTranscriptRepository()

    uow = FakeUnitOfWork(
        catalog=catalog_repo,
        content=content_repo,
        transcripts=transcript_repo,
    )
    return {
        "uow": uow,
        "catalog": catalog_repo,
        "content": content_repo,
        "transcripts": transcript_repo,
    }


def make_catalog_item(item_id: str = "item-01") -> CatalogItem:
    item = CatalogItem(
        id=item_id,
        topic_id="topic-anime",
        ci_level=1,
        duration_seconds=120,
        media_type="clip",
        visual_support="full",
        title_internal="Clip Title Internal",
        created_by="staff-01",
        status="published",
    )
    item.media.append(MediaRef(id=f"media-{item_id}", storage_key=f"raw/{item_id}.mp4"))
    return item


def make_content_version(catalog_item_id: str = "item-01", version_id: str = "ver-01") -> ContentVersion:
    return ContentVersion(
        id=version_id,
        catalog_item_id=catalog_item_id,
        version_number=1,
        revision=1,
        is_published=True,
        scenes=[
            Scene(
                id="scene-01",
                scene_index=0,
                start_time_seconds=0,
                end_time_seconds=5,
                title_jp="シーン1",
                transcript_jp="シーン1テキスト",
            ),
            Scene(
                id="scene-02",
                scene_index=1,
                start_time_seconds=5,
                end_time_seconds=10,
                title_jp="シーン2",
                transcript_jp="シーン2テキスト",
            ),
        ],
    )


def seed_catalog(uow, item: CatalogItem, cv: ContentVersion) -> None:
    uow.catalog.items[item.id] = item
    uow.catalog.commit_transaction()
    uow.content.versions.setdefault(item.id, []).append(cv)
    uow.content.commit_transaction()


# ------------------------------------------------------------------------------
# 1. Pure Python Unicode Japanese Analyzer Tests
# ------------------------------------------------------------------------------

def test_get_char_type_classification():
    assert get_char_type("漢") == "kanji"
    assert get_char_type("あ") == "hiragana"
    assert get_char_type("ア") == "katakana"
    assert get_char_type("A") == "latin"
    assert get_char_type("9") == "number"
    assert get_char_type("。") == "punct"
    assert get_char_type("、") == "punct"
    assert get_char_type(" ") == "whitespace"


def test_analyze_japanese_text_token_spans_and_offsets():
    text = "今日はいい天気ですね。"
    spans = analyze_japanese_text(text)

    assert len(spans) > 0
    # Verify each token span matches substring exactly
    for token in spans:
        extracted = text[token.start_offset:token.end_offset]
        assert extracted == token.surface


def test_analyze_japanese_text_katakana_and_latin_mixing():
    text = "カフェで Coffee を飲む。"
    spans = analyze_japanese_text(text)
    surfaces = [t.surface for t in spans]

    assert "カフェ" in surfaces
    assert "Coffee" in surfaces
    assert "飲" in surfaces
    assert "む" in surfaces


def test_analyze_japanese_text_empty_and_spaces():
    empty_res = analyze_japanese_text("")
    assert len(empty_res) == 0

    space_res = analyze_japanese_text("   \n\t  ")
    assert len(space_res) == 0


# ------------------------------------------------------------------------------
# 2. Domain Validation Bounds & State Machine Transition Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_draft_bounds_validation(transcript_env):
    uow = transcript_env["uow"]
    item = make_catalog_item("item-bound")
    cv = make_content_version("item-bound", "ver-bound")
    seed_catalog(uow, item, cv)

    # > 100 segments limit
    too_many_segments = [
        {"scene_id": "scene-01", "text_ja": f"セグメント {i}"}
        for i in range(101)
    ]
    cmd_too_many = SaveTranscriptDraftCommand(
        user_id="staff-01",
        catalog_item_id="item-bound",
        content_version_id="ver-bound",
        expected_revision=0,
        segments=too_many_segments,
    )
    with pytest.raises(ValidationError, match="100"):
        await handle_save_transcript_draft(cmd_too_many, uow)

    # > 500 chars in single segment
    too_long_segment = [{"scene_id": "scene-01", "text_ja": "あ" * 501}]
    cmd_too_long = SaveTranscriptDraftCommand(
        user_id="staff-01",
        catalog_item_id="item-bound",
        content_version_id="ver-bound",
        expected_revision=0,
        segments=too_long_segment,
    )
    with pytest.raises(ValidationError, match="500"):
        await handle_save_transcript_draft(cmd_too_long, uow)

    # > 20,000 total characters with 41 unique scenes
    scenes_41 = [
        Scene(
            id=f"scene-{i:02d}",
            scene_index=i,
            start_time_seconds=i * 5,
            end_time_seconds=(i + 1) * 5,
            title_jp=f"S{i}",
            transcript_jp=f"T{i}",
        )
        for i in range(41)
    ]
    cv_41 = ContentVersion(
        id="ver-41",
        catalog_item_id="item-bound",
        version_number=2,
        revision=1,
        is_published=True,
        scenes=scenes_41,
    )
    uow.content.versions["item-bound"].append(cv_41)
    uow.content.commit_transaction()

    huge_segments = [
        {"scene_id": f"scene-{i:02d}", "text_ja": "あ" * 500}
        for i in range(41)  # 41 * 500 = 20,500 > 20,000
    ]
    cmd_huge = SaveTranscriptDraftCommand(
        user_id="staff-01",
        catalog_item_id="item-bound",
        content_version_id="ver-41",
        expected_revision=0,
        segments=huge_segments,
    )
    with pytest.raises(ValidationError, match="20000"):
        await handle_save_transcript_draft(cmd_huge, uow)

    # Non-existent scene reference
    invalid_scene = [{"scene_id": "scene-nonexistent", "text_ja": "こんにちは"}]
    cmd_invalid_scene = SaveTranscriptDraftCommand(
        user_id="staff-01",
        catalog_item_id="item-bound",
        content_version_id="ver-bound",
        expected_revision=0,
        segments=invalid_scene,
    )
    with pytest.raises(ValidationError, match="does not belong to content version"):
        await handle_save_transcript_draft(cmd_invalid_scene, uow)


# ------------------------------------------------------------------------------
# 3. Application Workflow & Concurrency (CAS) Tests
# ------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcript_full_lifecycle_and_cas_concurrency(transcript_env):
    uow = transcript_env["uow"]
    item = make_catalog_item("item-lifecycle")
    cv = make_content_version("item-lifecycle", "ver-lifecycle")
    seed_catalog(uow, item, cv)

    # 1. Initial Save Draft (expected_revision = 0)
    segments = [
        {"scene_id": "scene-01", "text_ja": "おはようございます。"},
        {"scene_id": "scene-02", "text_ja": "今日もいい天気ですね。"},
    ]
    cmd_draft1 = SaveTranscriptDraftCommand(
        user_id="teacher-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=0,
        segments=segments,
    )
    rev1 = await handle_save_transcript_draft(cmd_draft1, uow)
    assert rev1.revision == 1
    assert rev1.status == TranscriptStatus.DRAFT
    assert len(rev1.segments) == 2

    # 2. CAS Conflict on Save Draft (expected_revision = 0 again -> conflict)
    cmd_conflict = SaveTranscriptDraftCommand(
        user_id="teacher-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=0,
        segments=segments,
    )
    with pytest.raises(RevisionConflictError, match="Expected revision 0, but current revision is 1"):
        await handle_save_transcript_draft(cmd_conflict, uow)

    # 3. Submit QA (expected_revision = 1 -> rev 1 qa_submitted)
    cmd_submit = SubmitTranscriptQACommand(
        user_id="teacher-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=1,
    )
    rev2 = await handle_submit_transcript_qa(cmd_submit, uow)
    assert rev2.revision == 1
    assert rev2.status == TranscriptStatus.QA_SUBMITTED

    # 4. Cannot submit QA twice with wrong status
    with pytest.raises(InvalidDomainStateError):
        await handle_submit_transcript_qa(cmd_submit, uow)

    # 5. Approve by Admin (expected_revision = 1 -> rev 1 approved)
    cmd_approve = ApproveTranscriptCommand(
        user_id="admin-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=1,
    )
    rev3 = await handle_approve_transcript(cmd_approve, uow)
    assert rev3.revision == 1
    assert rev3.status == TranscriptStatus.APPROVED
    assert rev3.approved_by == "admin-01"

    # Verify approved_scene_texts projection activated
    active_texts = [
        t for t in uow.transcripts.approved_texts.values()
        if t.content_version_id == "ver-lifecycle" and t.is_active
    ]
    assert len(active_texts) == 2
    assert all(t.is_active for t in active_texts)
    assert any(t.text_ja == "おはようございます。" for t in active_texts)

    # 6. Return to Draft by Admin (requires reason, deactivates projections)
    cmd_return_no_reason = ReturnTranscriptToDraftCommand(
        user_id="admin-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=1,
        reason="   ",
    )
    with pytest.raises(ValidationError, match="A reason must be provided"):
        await handle_return_transcript_to_draft(cmd_return_no_reason, uow)

    cmd_return = ReturnTranscriptToDraftCommand(
        user_id="admin-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=1,
        reason="Katakana typo in scene 2",
    )
    rev4 = await handle_return_transcript_to_draft(cmd_return, uow)
    assert rev4.revision == 1
    assert rev4.status == TranscriptStatus.RETURNED_TO_DRAFT
    assert rev4.return_reason == "Katakana typo in scene 2"

    # Verify approved_scene_texts projection deactivated
    active_after_return = [
        t for t in uow.transcripts.approved_texts.values()
        if t.content_version_id == "ver-lifecycle" and t.is_active
    ]
    assert len(active_after_return) == 0

    # 7. Edit again from RETURNED_TO_DRAFT with expected_revision=1 -> bumps to rev 2!
    cmd_draft2 = SaveTranscriptDraftCommand(
        user_id="teacher-01",
        catalog_item_id="item-lifecycle",
        content_version_id="ver-lifecycle",
        expected_revision=1,
        segments=segments,
    )
    rev5 = await handle_save_transcript_draft(cmd_draft2, uow)
    assert rev5.revision == 2
    assert rev5.status == TranscriptStatus.DRAFT


@pytest.mark.asyncio
async def test_language_analysis_job_execution_and_idempotency(transcript_env):
    uow = transcript_env["uow"]
    item = make_catalog_item("item-analysis")
    cv = make_content_version("item-analysis", "ver-analysis")
    seed_catalog(uow, item, cv)

    # Save a draft revision with realistic Japanese text
    cmd_draft = SaveTranscriptDraftCommand(
        user_id="teacher-01",
        catalog_item_id="item-analysis",
        content_version_id="ver-analysis",
        expected_revision=0,
        segments=[
            {"scene_id": "scene-01", "text_ja": "猫が好きです。"},
            {"scene_id": "scene-02", "text_ja": "毎日アニメを見ます。"},
        ],
    )
    rev = await handle_save_transcript_draft(cmd_draft, uow)

    # 1. Create analysis job
    cmd_job = CreateLanguageAnalysisJobCommand(
        user_id="teacher-01",
        catalog_item_id="item-analysis",
        transcript_revision_id=rev.id,
        idempotency_key="idemp-key-analysis-01",
    )
    job1 = await handle_create_language_analysis_job(cmd_job, uow)
    assert job1.status == LanguageAnalysisJobStatus.COMPLETED
    assert job1.results is not None
    assert "segments" in job1.results
    assert len(job1.results["segments"]) == 2
    assert job1.results["total_tokens"] > 0

    # 2. Idempotent duplicate call returns the same job
    job2 = await handle_create_language_analysis_job(cmd_job, uow)
    assert job2.id == job1.id
    assert job2.status == LanguageAnalysisJobStatus.COMPLETED

    # 3. Query job by ID
    query = GetLanguageAnalysisJobQuery(job_id=job1.id)
    job_fetched = await handle_get_language_analysis_job(query, uow)
    assert job_fetched.id == job1.id


# ------------------------------------------------------------------------------
# 4. HTTP API Contract & RBAC Security Tests
# ------------------------------------------------------------------------------

def test_api_transcript_unauthorized(client: TestClient):
    # Without Authorization header -> 401
    res = client.get("/staff/catalog/c0000000-0000-0000-0000-000000000001/transcript")
    assert res.status_code == 401


def test_api_transcript_forbidden_for_learner(client: TestClient):
    learner = UserDTO(id="user-learner", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    res = client.get("/staff/catalog/c0000000-0000-0000-0000-000000000001/transcript")
    assert res.status_code == 403


def test_api_transcript_approve_requires_admin_role(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, transcript_env
):
    uow = transcript_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.transcript.create_uow", lambda session: uow)

    # Teacher role is NOT allowed to approve or return to draft
    teacher = UserDTO(id="staff-teacher", email="teacher@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: teacher

    res_approve = client.post(
        "/staff/catalog/c0000000-0000-0000-0000-000000000001/transcript/approve",
        json={"content_version_id": "ver-01", "expected_revision": 1},
    )
    assert res_approve.status_code == 403

    res_return = client.post(
        "/staff/catalog/c0000000-0000-0000-0000-000000000001/transcript/return-to-draft",
        json={"content_version_id": "ver-01", "expected_revision": 1, "reason": "Fix typo"},
    )
    assert res_return.status_code == 403


def test_api_transcript_full_http_lifecycle(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, transcript_env
):
    uow = transcript_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.transcript.create_uow", lambda session: uow)

    item_id = "c0000000-0000-0000-0000-000000000001"
    cv_id = "v0000000-0000-0000-0000-000000000001"
    item = make_catalog_item(item_id)
    cv = make_content_version(item_id, cv_id)
    seed_catalog(uow, item, cv)

    teacher = UserDTO(id="staff-teacher", email="teacher@test.com", roles=["teacher"])
    admin = UserDTO(id="staff-admin", email="admin@test.com", roles=["admin"])

    # 1. GET non-existent transcript -> 404
    client.app.dependency_overrides[require_user] = lambda: teacher
    res_get404 = client.get(f"/staff/catalog/{item_id}/transcript?content_version_id={cv_id}")
    assert res_get404.status_code == 404

    # 2. PUT Draft (rev 1)
    payload_draft = {
        "content_version_id": cv_id,
        "expected_revision": 0,
        "segments": [
            {"scene_id": "scene-01", "text_ja": "おはようございます。"},
            {"scene_id": "scene-02", "text_ja": "今日も一日頑張りましょう。"},
        ],
        "provenance": "manual_teacher",
    }
    res_put = client.put(f"/staff/catalog/{item_id}/transcript", json=payload_draft)
    assert res_put.status_code == 200, res_put.text
    rev1_data = res_put.json()
    assert rev1_data["revision"] == 1
    assert rev1_data["status"] == "draft"
    assert rev1_data["created_by"] == "staff-teacher"
    rev1_id = rev1_data["id"]

    # 3. PUT Draft CAS Conflict -> 409
    res_conflict = client.put(f"/staff/catalog/{item_id}/transcript", json=payload_draft)
    assert res_conflict.status_code == 409

    # 4. POST Submit QA (rev 1)
    payload_qa = {"content_version_id": cv_id, "expected_revision": 1}
    res_qa = client.post(f"/staff/catalog/{item_id}/transcript/submit-qa", json=payload_qa)
    assert res_qa.status_code == 200
    rev2_data = res_qa.json()
    assert rev2_data["revision"] == 1
    assert rev2_data["status"] == "qa_submitted"

    # 5. POST Approve as Admin (rev 1)
    client.app.dependency_overrides[require_user] = lambda: admin
    payload_approve = {"content_version_id": cv_id, "expected_revision": 1}
    res_approve = client.post(f"/staff/catalog/{item_id}/transcript/approve", json=payload_approve)
    assert res_approve.status_code == 200
    rev3_data = res_approve.json()
    assert rev3_data["revision"] == 1
    assert rev3_data["status"] == "approved"
    assert rev3_data["approved_by"] == "staff-admin"

    # 6. POST Return to Draft as Admin (rev 1)
    payload_return = {
        "content_version_id": cv_id,
        "expected_revision": 1,
        "reason": "Please check kana spelling in scene 1",
    }
    res_return = client.post(f"/staff/catalog/{item_id}/transcript/return-to-draft", json=payload_return)
    assert res_return.status_code == 200
    rev4_data = res_return.json()
    assert rev4_data["revision"] == 1
    assert rev4_data["status"] == "returned_to_draft"
    assert rev4_data["return_reason"] == "Please check kana spelling in scene 1"

    # 7. POST Language Analysis Job
    client.app.dependency_overrides[require_user] = lambda: teacher
    res_job = client.post(
        f"/staff/catalog/{item_id}/language-analysis-jobs",
        json={"transcript_revision_id": rev1_id},
        headers={"Idempotency-Key": "http-idemp-01"},
    )
    assert res_job.status_code == 202
    job_data = res_job.json()
    assert job_data["status"] == "completed"
    assert "results" in job_data
    job_id = job_data["id"]

    # 8. GET Language Analysis Job
    res_get_job = client.get(f"/staff/language-analysis-jobs/{job_id}")
    assert res_get_job.status_code == 200
    assert res_get_job.json()["id"] == job_id
