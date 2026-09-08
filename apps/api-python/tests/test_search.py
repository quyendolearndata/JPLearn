"""Tests for Japanese Scene Search Projection and Endpoint (PR8b / UC-T10 / FR-SCH-001).

Validates:
1. Pure Python Domain Search Logic:
   - Unicode NFKC normalization and whitespace stripping (half-width to full-width Kana, full-width spaces)
   - Input length validation (1-100 characters)
   - Match kind classification: priority 1 `exact_phrase`, priority 2 `token_match`
   - Accurate Unicode code point highlight spans calculation
   - Cursor serialization with index generation pin
2. Application Handler Logic & Pedagogy/Security Boundaries (FR-NEG):
   - Capability switch `scene_search_enabled` (disabled -> 403 Forbidden)
   - Learner CI level constraint: search results never exceed learner's current CI level
   - Draft isolation: draft/unpublished items and versions are NEVER returned
   - Stale/revoked isolation: deactivated approved texts (`is_active = False`) are NEVER returned
   - Data privacy: zero leakage of `title_internal`, L1 translations, or grammar explanations
   - Keyset cursor pagination with generation pin (generation mismatch -> 409 Conflict)
3. HTTP API Contract & Route Precedence:
   - Authentication required (401)
   - Route precedence: `/catalog/search` is resolved before dynamic `/catalog/{id}`
   - End-to-end HTTP request and response contracts matching OpenAPI
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    ApproveTranscriptCommand,
    SaveTranscriptDraftCommand,
)
from jplearn_api.application.handlers.search import handle_search_scenes
from jplearn_api.application.handlers.transcript import (
    handle_approve_transcript,
    handle_save_transcript_draft,
)
from jplearn_api.application.queries import SearchScenesQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem, MediaRef
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import (
    ForbiddenError,
    RevisionConflictError,
    ValidationError,
)
from jplearn_api.domain.learning import LearnerProgress
from jplearn_api.domain.search import (
    calculate_highlights_and_match_kind,
    decode_search_cursor,
    encode_search_cursor,
    normalize_search_query,
    search_candidate_terms,
)
from jplearn_api.domain.transcript import ApprovedSceneText, TranscriptSegment
from jplearn_api.entrypoints.http.security import require_user
from jplearn_api.settings import Settings
from fakes import (
    FakeCatalogRepository,
    FakeContentRepository,
    FakeLearningRepository,
    FakeTranscriptRepository,
    FakeUnitOfWork,
)


# ==============================================================================
# 1. Pure Python Domain Search Logic Tests
# ==============================================================================

def test_normalize_search_query_valid():
    # Half-width katakana converted to full-width katakana
    assert normalize_search_query("ｺﾝﾆﾁﾊ") == "コンニチハ"
    # Full-width whitespace stripped
    assert normalize_search_query("　こんにちは　") == "こんにちは"
    # Mixed spaces and ascii
    assert normalize_search_query("  JP Learn  ") == "JP Learn"


def test_normalize_search_query_bounds():
    with pytest.raises(ValidationError, match="must not be empty"):
        normalize_search_query("")
    with pytest.raises(ValidationError, match="between 1 and 100 characters"):
        normalize_search_query("   　　  ")
    with pytest.raises(ValidationError, match="between 1 and 100 characters"):
        normalize_search_query("あ" * 101)


def test_search_candidate_terms_are_literal_and_deduplicated():
    assert search_candidate_terms("今日 良い天気 今日") == ["今日", "良い天気"]
    assert search_candidate_terms("%＿店") == ["店"]


def test_calculate_highlights_and_match_kind_exact():
    text = "こんにちは、元気ですか。本当に元気ですね！"
    match_kind, spans = calculate_highlights_and_match_kind(text, "元気")
    assert match_kind == "exact_phrase"
    assert len(spans) == 2
    assert spans[0] == {"start_offset": 6, "end_offset": 8}
    assert spans[1] == {"start_offset": 15, "end_offset": 17}
    # Verify slices in original text
    assert text[spans[0]["start_offset"]:spans[0]["end_offset"]] == "元気"
    assert text[spans[1]["start_offset"]:spans[1]["end_offset"]] == "元気"


def test_calculate_highlights_and_match_kind_token():
    text = "今日は、とても良い天気ですね。"
    # Query without punctuation matches tokens
    match_kind, spans = calculate_highlights_and_match_kind(text, "今日 良い天気")
    assert match_kind == "token_match"
    assert len(spans) == 2  # '今日' and '良い天気'
    for sp in spans:
        matched_str = text[sp["start_offset"]:sp["end_offset"]]
        assert len(matched_str) > 0


def test_calculate_highlights_and_match_kind_no_match():
    text = "おはようございます。"
    match_kind, spans = calculate_highlights_and_match_kind(text, "こんばんは")
    assert match_kind is None
    assert spans == []


def test_search_cursor_roundtrip():
    encoded = encode_search_cursor(generation="gen_2026", offset=40)
    gen, offset = decode_search_cursor(encoded)
    assert gen == "gen_2026"
    assert offset == 40

    with pytest.raises(ValidationError, match="Invalid search cursor"):
        decode_search_cursor("invalid_base64_???")


# ==============================================================================
# 2. Application Handler & Security Invariants Tests (FR-NEG)
# ==============================================================================

@pytest.fixture
def search_test_env():
    catalog_repo = FakeCatalogRepository()
    content_repo = FakeContentRepository()
    transcript_repo = FakeTranscriptRepository()
    learning_repo = FakeLearningRepository()

    uow = FakeUnitOfWork(
        catalog=catalog_repo,
        content=content_repo,
        transcripts=transcript_repo,
        learning=learning_repo,
    )
    return {
        "uow": uow,
        "catalog": catalog_repo,
        "content": content_repo,
        "transcripts": transcript_repo,
        "learning": learning_repo,
    }


def set_learner_progress(learning_repo, progress: LearnerProgress) -> None:
    learning_repo.progress[progress.user_id] = progress
    learning_repo._committed_progress[progress.user_id] = progress


def commit_fixture_data(uow: FakeUnitOfWork) -> None:
    for p in uow.participants:
        if hasattr(p, "commit_transaction"):
            p.commit_transaction()



@pytest.mark.asyncio
async def test_search_disabled_returns_forbidden(search_test_env):
    uow = search_test_env["uow"]
    query = SearchScenesQuery(q="こんにちは", user_id="user-01")
    with pytest.raises(ForbiddenError, match="Scene search is currently disabled"):
        await handle_search_scenes(query, uow, search_enabled=False)


@pytest.mark.asyncio
async def test_search_exact_match_success(search_test_env):
    uow = search_test_env["uow"]
    now = datetime.now(timezone.utc)

    # 1. Setup Published Catalog Item (CI Level 1)
    item = CatalogItem(
        id="cat-01",
        topic_id="daily_greeting",
        ci_level=1,
        duration_seconds=120,
        media_type="video",
        visual_support="video",
        title_internal="Internal Secret Greeting Title",
        status="published",
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item.id] = item

    # 2. Setup Published Content Version with Scene
    scene = Scene(
        id="scn-01",
        scene_index=1,
        start_time_seconds=0,
        end_time_seconds=10,
        title_jp="挨拶の場面",
        transcript_jp="こんにちは、元気ですか。",
    )
    version = ContentVersion(
        id="ver-01",
        catalog_item_id="cat-01",
        version_number=1,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=[scene],
    )
    search_test_env["content"].versions.setdefault(version.catalog_item_id, []).append(version)

    # 3. Setup Approved Scene Text projection
    ast = ApprovedSceneText(
        id="ast-01",
        catalog_item_id="cat-01",
        content_version_id="ver-01",
        scene_id="scn-01",
        transcript_revision_id="rev-01",
        text_ja="こんにちは、元気ですか。",
        scene_index=1,
        start_time_seconds=0,
        end_time_seconds=10,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    search_test_env["transcripts"].approved_texts[ast.id] = ast

    # 4. Setup Learner progress (CI Level 1)
    progress = LearnerProgress(
        user_id="learner-01",
        current_ci_level=1,
        minutes_comprehensible=300,
    )
    set_learner_progress(search_test_env["learning"], progress)
    commit_fixture_data(uow)

    # Search with exact phrase
    query = SearchScenesQuery(q="元気ですか", user_id="learner-01")
    res = await handle_search_scenes(query, uow, search_enabled=True)

    assert len(res.items) == 1
    item_res = res.items[0]
    assert item_res.catalog_item_id == "cat-01"
    assert item_res.content_version_id == "ver-01"
    assert item_res.scene_id == "scn-01"
    assert item_res.scene_index == 1
    assert item_res.match_kind == "exact_phrase"
    assert item_res.title_jp == "挨拶の場面"
    assert item_res.ci_level == 1
    assert item_res.topic_id == "daily_greeting"
    assert len(item_res.highlight_spans) == 1
    span = item_res.highlight_spans[0]
    assert span["start_offset"] == 6
    assert span["end_offset"] == 11


@pytest.mark.asyncio
async def test_search_ci_level_enforcement(search_test_env):
    uow = search_test_env["uow"]
    now = datetime.now(timezone.utc)

    # Cat 1 (CI 1 - published)
    item1 = CatalogItem(
        id="cat-ci1",
        topic_id="topic-1",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="video",
        title_internal="Internal 1",
        status="published",
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item1.id] = item1

    # Cat 2 (CI 2 - published)
    item2 = CatalogItem(
        id="cat-ci2",
        topic_id="topic-2",
        ci_level=2,
        duration_seconds=60,
        media_type="video",
        visual_support="video",
        title_internal="Internal 2",
        status="published",
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item2.id] = item2

    for cat_id, ver_id, scn_id, ast_id in [
        ("cat-ci1", "ver-ci1", "scn-ci1", "ast-ci1"),
        ("cat-ci2", "ver-ci2", "scn-ci2", "ast-ci2"),
    ]:
        sc = Scene(
            id=scn_id,
            scene_index=1,
            start_time_seconds=0,
            end_time_seconds=10,
            title_jp="場面",
            transcript_jp="猫が好きです。",
        )
        ver = ContentVersion(
            id=ver_id,
            catalog_item_id=cat_id,
            version_number=1,
            revision=1,
            is_frozen=True,
            is_published=True,
            scenes=[sc],
        )
        search_test_env["content"].versions.setdefault(ver.catalog_item_id, []).append(ver)
        ast = ApprovedSceneText(
            id=ast_id,
            catalog_item_id=cat_id,
            content_version_id=ver_id,
            scene_id=scn_id,
            transcript_revision_id="rev-01",
            text_ja="猫が好きです。",
            scene_index=1,
            start_time_seconds=0,
            end_time_seconds=10,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        search_test_env["transcripts"].approved_texts[ast.id] = ast

    # Learner CI level is 1
    progress = LearnerProgress(
        user_id="learner-ci1",
        current_ci_level=1,
        minutes_comprehensible=100,
    )
    set_learner_progress(search_test_env["learning"], progress)
    commit_fixture_data(uow)

    # Query without filter: must only return cat-ci1
    res1 = await handle_search_scenes(
        SearchScenesQuery(q="猫", user_id="learner-ci1"),
        uow,
        search_enabled=True,
    )
    assert len(res1.items) == 1
    assert res1.items[0].catalog_item_id == "cat-ci1"

    # Query explicitly asking for ci_level=2: must still clamp to learner level (1)
    res2 = await handle_search_scenes(
        SearchScenesQuery(q="猫", user_id="learner-ci1", ci_level=2),
        uow,
        search_enabled=True,
    )
    assert len(res2.items) == 1
    assert res2.items[0].catalog_item_id == "cat-ci1"


@pytest.mark.asyncio
async def test_search_security_invariants_fr_neg(search_test_env):
    """Verify that draft/unpublished items, deactivated approved texts are excluded, and no internal data leaked."""
    uow = search_test_env["uow"]
    now = datetime.now(timezone.utc)

    # 1. Draft catalog item
    item_draft = CatalogItem(
        id="cat-draft",
        topic_id="topic-draft",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="video",
        title_internal="SECRET_DRAFT_TITLE",
        status="draft",  # NOT published
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item_draft.id] = item_draft
    sc_draft = Scene(id="scn-d", scene_index=1, start_time_seconds=0, end_time_seconds=10, title_jp="下書き", transcript_jp="リンゴを食べる。")
    ver_draft = ContentVersion(id="ver-d", catalog_item_id="cat-draft", version_number=1, revision=1, is_frozen=False, is_published=False, scenes=[sc_draft])
    search_test_env["content"].versions.setdefault(ver_draft.catalog_item_id, []).append(ver_draft)
    ast_draft = ApprovedSceneText(id="ast-d", catalog_item_id="cat-draft", content_version_id="ver-d", scene_id="scn-d", transcript_revision_id="rev-d", text_ja="リンゴを食べる。", scene_index=1, start_time_seconds=0, end_time_seconds=10, is_active=True, created_at=now, updated_at=now)
    search_test_env["transcripts"].approved_texts[ast_draft.id] = ast_draft

    # 2. Deactivated text (returned to draft)
    item_pub = CatalogItem(
        id="cat-revoked",
        topic_id="topic-revoked",
        ci_level=1,
        duration_seconds=60,
        media_type="video",
        visual_support="video",
        title_internal="SECRET_REVOKED_TITLE",
        status="published",
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item_pub.id] = item_pub
    sc_rev = Scene(id="scn-r", scene_index=1, start_time_seconds=0, end_time_seconds=10, title_jp="取下げ", transcript_jp="リンゴを食べる。")
    ver_rev = ContentVersion(id="ver-r", catalog_item_id="cat-revoked", version_number=1, revision=1, is_frozen=True, is_published=True, scenes=[sc_rev])
    search_test_env["content"].versions.setdefault(ver_rev.catalog_item_id, []).append(ver_rev)
    ast_rev = ApprovedSceneText(id="ast-r", catalog_item_id="cat-revoked", content_version_id="ver-r", scene_id="scn-r", transcript_revision_id="rev-r", text_ja="リンゴを食べる。", scene_index=1, start_time_seconds=0, end_time_seconds=10, is_active=False, created_at=now, updated_at=now)  # is_active = False!
    search_test_env["transcripts"].approved_texts[ast_rev.id] = ast_rev

    # Learner progress CI 1
    set_learner_progress(
        search_test_env["learning"],
        LearnerProgress(user_id="user-check", current_ci_level=1, minutes_comprehensible=100),
    )
    commit_fixture_data(uow)

    # Search for "リンゴ"
    res = await handle_search_scenes(SearchScenesQuery(q="リンゴ", user_id="user-check"), uow, search_enabled=True)
    # Neither draft nor deactivated text should appear
    assert len(res.items) == 0


@pytest.mark.asyncio
async def test_search_cursor_pagination_and_generation_pin(search_test_env):
    uow = search_test_env["uow"]
    t0 = datetime(2026, 9, 7, 10, 0, 0)

    # Published catalog item
    item = CatalogItem(
        id="cat-multi",
        topic_id="topic-multi",
        ci_level=1,
        duration_seconds=180,
        media_type="video",
        visual_support="video",
        title_internal="Internal",
        status="published",
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item.id] = item

    scenes = [
        Scene(id=f"scn-{i}", scene_index=i, start_time_seconds=i * 10, end_time_seconds=(i + 1) * 10, title_jp=f"場面{i}", transcript_jp=f"富士山が見える{i}")
        for i in range(1, 4)
    ]
    ver = ContentVersion(
        id="ver-multi",
        catalog_item_id="cat-multi",
        version_number=1,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=scenes,
    )
    search_test_env["content"].versions.setdefault(ver.catalog_item_id, []).append(ver)

    for sc in scenes:
        ast = ApprovedSceneText(
            id=f"ast-{sc.scene_index}",
            catalog_item_id="cat-multi",
            content_version_id="ver-multi",
            scene_id=sc.id,
            transcript_revision_id="rev-01",
            text_ja=sc.transcript_jp,
            scene_index=sc.scene_index,
            start_time_seconds=sc.start_time_seconds,
            end_time_seconds=sc.end_time_seconds,
            is_active=True,
            created_at=t0,
            updated_at=t0,
        )
        search_test_env["transcripts"].approved_texts[ast.id] = ast

    set_learner_progress(
        search_test_env["learning"],
        LearnerProgress(user_id="learner-p", current_ci_level=1, minutes_comprehensible=100),
    )
    commit_fixture_data(uow)

    # 1. Page 1 (limit=1)
    q1 = SearchScenesQuery(q="富士山", user_id="learner-p", limit=1)
    res1 = await handle_search_scenes(q1, uow, search_enabled=True)
    assert len(res1.items) == 1
    assert res1.items[0].scene_index == 1
    assert res1.next_cursor is not None

    # 2. Page 2 (with cursor, limit=1)
    q2 = SearchScenesQuery(q="富士山", user_id="learner-p", cursor=res1.next_cursor, limit=1)
    res2 = await handle_search_scenes(q2, uow, search_enabled=True)
    assert len(res2.items) == 1
    assert res2.items[0].scene_index == 2
    assert res2.next_cursor is not None

    # 3. Modify generation: simulate new approved revision timestamp update
    t1 = datetime(2026, 9, 7, 12, 0, 0)
    search_test_env["transcripts"].approved_texts["ast-1"].updated_at = t1
    commit_fixture_data(uow)

    # 4. Reusing old cursor from res1/res2 now raises RevisionConflictError (409)
    q_stale = SearchScenesQuery(q="富士山", user_id="learner-p", cursor=res2.next_cursor, limit=1)
    with pytest.raises(RevisionConflictError, match="Index generation mismatch"):
        await handle_search_scenes(q_stale, uow, search_enabled=True)


# ==============================================================================
# 3. HTTP API Contract & Route Precedence Tests
# ==============================================================================

def test_api_search_unauthorized(client: TestClient):
    res = client.get("/catalog/search?q=こんにちは")
    assert res.status_code == 401
    assert res.json()["statusCode"] == 401


def test_api_search_capability_disabled_returns_403(client: TestClient):
    learner = UserDTO(id="learner-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    # By default, scene_search_enabled is False
    res = client.get("/catalog/search?q=こんにちは")
    assert res.status_code == 403
    assert "disabled" in res.json()["message"]


def test_api_search_route_precedence(client: TestClient):
    """Ensures /catalog/search is NOT parsed as /catalog/{id} resulting in a UUID error."""
    learner = UserDTO(id="learner-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    res = client.get("/catalog/search?q=test")
    # Must be 403 (capability check) or 200 (if enabled), NEVER 422 with "value is not a valid uuid"
    assert res.status_code in (200, 403)
    if res.status_code == 403:
        assert "UUID" not in res.text


def test_api_search_query_validation(client: TestClient):
    learner = UserDTO(id="learner-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    # Missing q parameter -> 400
    res_missing = client.get("/catalog/search")
    assert res_missing.status_code == 400

    # Empty q parameter -> 400
    res_empty = client.get("/catalog/search?q=")
    assert res_empty.status_code == 400


def test_api_search_end_to_end_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, search_test_env
):
    uow = search_test_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.catalog.create_uow", lambda session: uow)
    client.app.state.settings.scene_search_enabled = True

    learner = UserDTO(id="user-learner-e2e", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    now = datetime.now(timezone.utc)
    item = CatalogItem(
        id="c0000000-0000-0000-0000-000000000099",
        topic_id="nature_tokyo",
        ci_level=1,
        duration_seconds=120,
        media_type="video",
        visual_support="video",
        title_internal="SECRET_CMS_TITLE",
        status="published",
        created_by="staff-01",
    )
    search_test_env["catalog"].items[item.id] = item

    sc = Scene(
        id="s0000000-0000-0000-0000-000000000099",
        scene_index=1,
        start_time_seconds=0,
        end_time_seconds=15,
        title_jp="桜の公園",
        transcript_jp="春になると、桜が綺麗に咲きます。",
    )
    ver = ContentVersion(
        id="v0000000-0000-0000-0000-000000000099",
        catalog_item_id=item.id,
        version_number=1,
        revision=1,
        is_frozen=True,
        is_published=True,
        scenes=[sc],
    )
    search_test_env["content"].versions.setdefault(ver.catalog_item_id, []).append(ver)

    ast = ApprovedSceneText(
        id="ast-e2e-01",
        catalog_item_id=item.id,
        content_version_id=ver.id,
        scene_id=sc.id,
        transcript_revision_id="rev-01",
        text_ja=sc.transcript_jp,
        scene_index=1,
        start_time_seconds=0,
        end_time_seconds=15,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    search_test_env["transcripts"].approved_texts[ast.id] = ast
    set_learner_progress(
        search_test_env["learning"],
        LearnerProgress(user_id="user-learner-e2e", current_ci_level=1, minutes_comprehensible=500),
    )
    commit_fixture_data(uow)

    # Execute search
    res = client.get("/catalog/search?q=桜が綺麗")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) == 1

    item_data = data["items"][0]
    assert item_data["catalog_item_id"] == item.id
    assert item_data["title_jp"] == "桜の公園"
    assert "SECRET_CMS_TITLE" not in res.text
    assert item_data["matched_text_ja"] == "春になると、桜が綺麗に咲きます。"
    assert item_data["match_kind"] == "exact_phrase"
    assert len(item_data["highlight_spans"]) == 1
    assert item_data["highlight_spans"][0]["start_offset"] == 6
    assert item_data["highlight_spans"][0]["end_offset"] == 10
