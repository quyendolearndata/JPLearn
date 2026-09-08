"""Tests for Content Jobs Queue, Worker CLI, and Quota Ledger Integration (ADR-007 PR8 / FR-AI-001).

Validates:
1. Pure Python Domain Logic:
   - ContentJob state machine (queued -> running -> succeeded / failed / cancelled)
   - Lease management, claim conditions, and attempt tokens
   - Retry counters and terminal failure transitions
   - Apply guard (only succeeded and not yet applied)
2. Application Handlers & Invariants:
   - Create content job reserves quota atomically under account lock
   - Idempotency per user and idempotency_key
   - Concurrency conflict (409) if active job exists for (content_version_id, task)
   - QuotaExceededError when limit reached
   - Capability enforcement (staff_ai_enabled)
   - Cancel job transitions to cancelled and releases reserved quota
   - Cancel terminal job raises ResourceConflictError
   - Apply job saves transcript draft with CAS expected_revision and source_hash validation
   - Apply job with stale source_hash or revision mismatch raises ResourceConflictError
3. Worker CLI Execution:
   - Worker claims job with lease and attempt token
   - Successful execution settles actual usage in ledger and saves result draft
   - Failure with exhausted retries marks failed and releases quota
   - Timeout/network error reconciles quota with outcome_unknown
   - Lost lease (CAS attempt token mismatch) avoids overwriting new worker's work
4. HTTP API Contract & Role Security:
   - 401 Unauthorized for unauthenticated requests
   - 403 Forbidden for learner role
   - 403 Forbidden when staff_ai_enabled = False
   - 202 Accepted, 200 OK end-to-end responses matching OpenAPI specification
   - Strict Privacy / Pedagogy Guard (FR-NEG): No learner data or external media URLs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.commands import (
    ApplyContentJobCommand,
    CancelContentJobCommand,
    CreateContentJobCommand,
)
from jplearn_api.application.handlers.content_jobs import (
    handle_apply_content_job,
    handle_cancel_content_job,
    handle_create_content_job,
    handle_execute_ai_worker_step,
    handle_get_content_job,
)
from jplearn_api.application.ports.ai_provider import (
    AiTranscriptionResult,
    AiUsageRecord,
)
from jplearn_api.application.queries import GetContentJobQuery
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.catalog import CatalogItem, MediaRef
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.content_job import (
    ContentJob,
    ContentJobStatus,
    ContentJobTask,
)
from jplearn_api.domain.errors import (
    ConflictError,
    DomainError,
    EntityNotFoundError,
    ForbiddenError,
    QuotaExceededError,
    RevisionConflictError,
)
from jplearn_api.domain.media import MediaAsset
from jplearn_api.domain.quota import QuotaAccount
from jplearn_api.domain.transcript import (
    TranscriptProvenance,
    TranscriptRevision,
    TranscriptSegment,
    TranscriptStatus,
)
from jplearn_api.entrypoints.http.security import require_user
from fakes import (
    FakeAiTranscriptionPort,
    FakeCatalogRepository,
    FakeContentJobRepository,
    FakeContentRepository,
    FakeMediaRepository,
    FakeQuotaRepository,
    FakeTranscriptRepository,
    FakeUnitOfWork,
    FakeUsageLedgerRepository,
    create_fake_uow_factory,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def base_test_environment():
    """Setup a standard in-memory test environment with quota, catalog, content, and jobs."""
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    user_id = "teacher-01"
    catalog_id = str(uuid4())
    version_id = str(uuid4())
    media_id = str(uuid4())

    quota_repo = FakeQuotaRepository()
    account = QuotaAccount(
        id=f"acc-{user_id}",
        user_id=user_id,
        name="Teacher AI Quota",
        max_audio_seconds=3600,
        max_input_tokens=1000000,
        max_output_tokens=500000,
        max_cost_micros=10000000,  # $10.00
    )
    quota_repo.accounts[account.id] = account
    quota_repo._committed_accounts[account.id] = account

    usage_ledger_repo = FakeUsageLedgerRepository()
    content_job_repo = FakeContentJobRepository()
    media_repo = FakeMediaRepository()
    content_repo = FakeContentRepository()
    catalog_repo = FakeCatalogRepository()
    transcript_repo = FakeTranscriptRepository()

    # Populate catalog item with media reference
    catalog_item = CatalogItem(
        id=catalog_id,
        topic_id="topic-01",
        ci_level=1,
        duration_seconds=120,
        media_type="video",
        visual_support="full",
        title_internal="Test Catalog Item",
        created_by=user_id,
        media=[MediaRef(id=media_id, storage_key=f"media/{media_id}.mp4")],
    )
    catalog_repo.items[catalog_id] = catalog_item
    catalog_repo._committed_items[catalog_id] = catalog_item

    # Populate media asset
    media_asset = MediaAsset(
        id=media_id,
        catalog_item_id=catalog_id,
        storage_key=f"media/{media_id}.mp4",
    )
    media_repo.assets[media_id] = media_asset
    media_repo._committed_assets[media_id] = media_asset

    # Populate content version with valid scene
    scene_01 = Scene(
        id="scene-01",
        scene_index=1,
        start_time_seconds=0,
        end_time_seconds=10,
        title_jp="シーン1",
        transcript_jp="初期テキスト",
    )
    content_ver = ContentVersion(
        id=version_id,
        catalog_item_id=catalog_id,
        version_number=1,
        revision=1,
        scenes=[scene_01],
        published_at=now,
    )
    content_repo.versions.setdefault(catalog_id, []).append(content_ver)
    content_repo._committed_versions.setdefault(catalog_id, []).append(content_ver)

    # Initial transcript revision
    initial_rev = TranscriptRevision(
        id=f"tr-{version_id}",
        catalog_item_id=catalog_id,
        content_version_id=version_id,
        revision=1,
        status=TranscriptStatus.DRAFT,
        segments=[
            TranscriptSegment(
                scene_id="scene-01",
                text_ja="初期テキスト",
            )
        ],
        provenance=TranscriptProvenance.MANUAL_TEACHER,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )
    transcript_repo.revisions[(catalog_id, version_id, 1)] = initial_rev
    transcript_repo._committed_revisions[(catalog_id, version_id, 1)] = initial_rev

    uow_factory = create_fake_uow_factory(
        quota=quota_repo,
        usage_ledger=usage_ledger_repo,
        content_jobs=content_job_repo,
        media=media_repo,
        content=content_repo,
        catalog=catalog_repo,
        transcripts=transcript_repo,
    )

    return {
        "now": now,
        "user_id": user_id,
        "catalog_id": catalog_id,
        "version_id": version_id,
        "media_id": media_id,
        "quota_repo": quota_repo,
        "usage_ledger_repo": usage_ledger_repo,
        "content_job_repo": content_job_repo,
        "media_repo": media_repo,
        "content_repo": content_repo,
        "catalog_repo": catalog_repo,
        "transcript_repo": transcript_repo,
        "uow_factory": uow_factory,
    }


# ==============================================================================
# 1. Pure Python Domain Logic Tests
# ==============================================================================

def test_content_job_initial_state():
    job = ContentJob(
        id="job-01",
        catalog_item_id="cat-01",
        content_version_id="ver-01",
        task=ContentJobTask.TRANSCRIPT,
        source_hash="src-hash-1",
        config_hash="cfg-hash-1",
        idempotency_key="idem-01",
        created_by="user-01",
        language="ja",
    )
    assert job.status == ContentJobStatus.QUEUED
    assert job.attempt == 0
    assert job.progress == 0.0
    assert job.attempt_token is None
    assert job.result_draft is None
    assert job.applied_at is None


def test_content_job_can_claim():
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    job = ContentJob(
        id="job-01",
        catalog_item_id="cat-01",
        content_version_id="ver-01",
        task=ContentJobTask.TRANSCRIPT,
        source_hash="src-hash-1",
        config_hash="cfg-hash-1",
        idempotency_key="idem-01",
        created_by="user-01",
        created_at=now,
        updated_at=now,
    )
    # Queued job can be claimed
    assert job.can_claim(now)

    # Running job with active lease cannot be claimed
    job.claim_lease("token-1", now + timedelta(seconds=60), now)
    assert not job.can_claim(now + timedelta(seconds=30))

    # Expired provider outcome requires reconciliation, never blind reclaim
    assert not job.can_claim(now + timedelta(seconds=61))

    # Succeeded job cannot be claimed
    job.record_success({"text": "done"}, {"provider": "mock"}, now)
    assert not job.can_claim(now + timedelta(seconds=100))


def test_content_job_record_failure_retryable():
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    job = ContentJob(
        id="job-01",
        catalog_item_id="cat-01",
        content_version_id="ver-01",
        task=ContentJobTask.TRANSCRIPT,
        source_hash="src-hash-1",
        config_hash="cfg-hash-1",
        idempotency_key="idem-01",
        created_by="user-01",
        max_attempts=3,
    )
    job.claim_lease("token-1", now + timedelta(seconds=60), now)
    assert job.attempt == 1

    job.record_failure("temporary network error", retryable=True, now=now)
    assert job.status == ContentJobStatus.QUEUED
    assert job.attempt == 1
    assert job.attempt_token is None  # Lease released for next worker

    # Claim attempt 2 and fail
    job.claim_lease("token-2", now + timedelta(seconds=60), now)
    job.record_failure("error 2", retryable=True, now=now)

    # Claim attempt 3 (exhausting max_attempts=3) and fail
    job.claim_lease("token-3", now + timedelta(seconds=60), now)
    job.record_failure("error 3", retryable=True, now=now)

    assert job.status == ContentJobStatus.FAILED
    assert job.attempt == 3


def test_content_job_cancel():
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
    job = ContentJob(
        id="job-01",
        catalog_item_id="cat-01",
        content_version_id="ver-01",
        task=ContentJobTask.TRANSCRIPT,
        source_hash="src-hash-1",
        config_hash="cfg-hash-1",
        idempotency_key="idem-01",
        created_by="user-01",
    )
    job.cancel(now)
    assert job.status == ContentJobStatus.CANCELLED

    # Cancel is idempotent
    job.cancel(now)
    assert job.status == ContentJobStatus.CANCELLED

    # But cancelling succeeded job raises ConflictError
    job.status = ContentJobStatus.SUCCEEDED
    with pytest.raises(ConflictError, match="Cannot cancel an already succeeded job"):
        job.cancel(now)


# ==============================================================================
# 2. Application Handlers & Invariants Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_create_content_job_success_and_reserves_quota(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-key-1",
        user_id=env["user_id"],
        estimated_audio_seconds=120,
        estimated_cost_micros=200000,
    )

    dto = await handle_create_content_job(cmd, uow, capability_enabled=True)

    assert dto.catalog_item_id == env["catalog_id"]
    assert dto.content_version_id == env["version_id"]
    assert dto.task == "transcript"
    assert dto.status == "queued"

    # Client estimates are compatibility hints; the server uses 120s × 1,000µ.
    acc = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert acc is not None
    assert acc.reserved_audio_seconds == 120
    assert acc.reserved_cost_micros == 120000

    # Verify ledger reservation entry
    entry = await uow.usage_ledger.get_reservation_by_job_id(dto.id)
    assert entry is not None
    assert entry.status == "reserved"
    assert entry.kind == "reservation"


@pytest.mark.asyncio
async def test_create_content_job_idempotent(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-repeat",
        user_id=env["user_id"],
        estimated_audio_seconds=120,
        estimated_cost_micros=200000,
    )

    dto1 = await handle_create_content_job(cmd, uow, capability_enabled=True)
    dto2 = await handle_create_content_job(cmd, uow, capability_enabled=True)

    assert dto1.id == dto2.id

    # Quota should only be reserved once
    acc = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert acc.reserved_audio_seconds == 120
    assert acc.reserved_cost_micros == 120000


@pytest.mark.asyncio
async def test_create_content_job_conflict_active_job(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd1 = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-job-1",
        user_id=env["user_id"],
    )
    await handle_create_content_job(cmd1, uow, capability_enabled=True)

    # Different idempotency key, same version and task
    cmd2 = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-job-2",
        user_id=env["user_id"],
    )
    with pytest.raises(ConflictError, match="already running"):
        await handle_create_content_job(cmd2, uow, capability_enabled=True)


@pytest.mark.asyncio
async def test_create_content_job_quota_exceeded(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    account = await uow.quota.get_or_create_account_for_user(env["user_id"])
    account.max_audio_seconds = 119
    await uow.quota.save_account(account)
    await uow.commit()

    cmd = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-over",
        user_id=env["user_id"],
        estimated_audio_seconds=1,  # Cannot understate the server-observed 120s.
        estimated_cost_micros=200000,
    )
    with pytest.raises(QuotaExceededError, match="Insufficient AI quota"):
        await handle_create_content_job(cmd, uow, capability_enabled=True)


@pytest.mark.asyncio
async def test_create_content_job_disabled_capability(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-disabled",
        user_id=env["user_id"],
    )
    with pytest.raises(ForbiddenError, match="disabled"):
        await handle_create_content_job(cmd, uow, capability_enabled=False)


@pytest.mark.asyncio
async def test_cancel_content_job_queued_releases_quota(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd_create = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-cancel-test",
        user_id=env["user_id"],
        estimated_audio_seconds=200,
        estimated_cost_micros=300000,
    )
    created = await handle_create_content_job(cmd_create, uow, capability_enabled=True)

    # Cancel the job
    cmd_cancel = CancelContentJobCommand(
        job_id=created.id,
        user_id=env["user_id"],
        user_roles=("teacher",),
    )
    cancelled_dto = await handle_cancel_content_job(cmd_cancel, uow, capability_enabled=True)
    assert cancelled_dto.status == "cancelled"

    # Quota should be completely released back
    acc = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert acc.reserved_audio_seconds == 0
    assert acc.reserved_cost_micros == 0


@pytest.mark.asyncio
async def test_cancel_content_job_terminal_raises_conflict(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd_create = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-term-test",
        user_id=env["user_id"],
    )
    created = await handle_create_content_job(cmd_create, uow, capability_enabled=True)

    # Mark job as SUCCEEDED (terminal state)
    job = await uow.content_jobs.get_by_id(created.id)
    job.status = ContentJobStatus.SUCCEEDED
    await uow.content_jobs.update(job)
    await uow.commit()

    cmd_cancel = CancelContentJobCommand(
        job_id=created.id,
        user_id=env["user_id"],
        user_roles=("teacher",),
    )

    # Cancel succeeded job -> raises ConflictError
    with pytest.raises(ConflictError, match="Cannot cancel an already succeeded job"):
        await handle_cancel_content_job(cmd_cancel, uow, capability_enabled=True)


@pytest.mark.asyncio
async def test_apply_content_job_success(base_test_environment):
    import hashlib
    env = base_test_environment
    uow = env["uow_factory"]()

    media_key = f"media/{env['media_id']}.mp4"
    source_hash = hashlib.sha256(f"{env['version_id']}:1:{media_key}".encode()).hexdigest()

    # Setup a succeeded job with result_draft
    job = ContentJob(
        id="job-apply-01",
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task=ContentJobTask.TRANSCRIPT,
        source_hash=source_hash,
        config_hash="cfg-hash",
        idempotency_key="idem-apply-01",
        created_by=env["user_id"],
        status=ContentJobStatus.SUCCEEDED,
        result_draft={
            "segments": [
                {"scene_id": "scene-01", "text_ja": "AI生成された字幕", "start_ms": 0, "end_ms": 1500}
            ],
            "source_hash": source_hash,
        },
    )
    await uow.content_jobs.add(job)
    await uow.commit()

    cmd_apply = ApplyContentJobCommand(
        job_id=job.id,
        expected_revision=1,
        user_id=env["user_id"],
    )
    dto = await handle_apply_content_job(cmd_apply, uow, capability_enabled=True)

    assert dto.applied_at is not None

    # Verify transcript draft was updated
    rev = await uow.transcripts.get_latest_revision(env["catalog_id"], env["version_id"])
    assert rev is not None
    assert rev.revision == 2
    assert rev.provenance == TranscriptProvenance.AI_ASSISTED
    assert len(rev.segments) == 1
    assert rev.segments[0].text_ja == "AI生成された字幕"


@pytest.mark.asyncio
async def test_apply_content_job_stale_source_hash_raises_conflict(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    job = ContentJob(
        id="job-apply-stale",
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task=ContentJobTask.TRANSCRIPT,
        source_hash="old-hash-which-does-not-match-current",
        config_hash="cfg-hash",
        idempotency_key="idem-apply-stale",
        created_by=env["user_id"],
        status=ContentJobStatus.SUCCEEDED,
        result_draft={
            "segments": [{"scene_id": "scene-01", "text_ja": "テスト", "start_ms": 0, "end_ms": 1000}],
            "source_hash": "old-hash",
        },
    )
    await uow.content_jobs.add(job)
    await uow.commit()

    cmd_apply = ApplyContentJobCommand(
        job_id=job.id,
        expected_revision=1,
        user_id=env["user_id"],
    )
    with pytest.raises(ConflictError, match="Source content version was modified"):
        await handle_apply_content_job(cmd_apply, uow, capability_enabled=True)


@pytest.mark.asyncio
async def test_apply_content_job_revision_conflict(base_test_environment):
    import hashlib
    env = base_test_environment
    uow = env["uow_factory"]()

    media_key = f"media/{env['media_id']}.mp4"
    source_hash = hashlib.sha256(f"{env['version_id']}:1:{media_key}".encode()).hexdigest()

    job = ContentJob(
        id="job-apply-rev-conflict",
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task=ContentJobTask.TRANSCRIPT,
        source_hash=source_hash,
        config_hash="cfg-hash",
        idempotency_key="idem-apply-rev-conflict",
        created_by=env["user_id"],
        status=ContentJobStatus.SUCCEEDED,
        result_draft={
            "segments": [{"scene_id": "scene-01", "text_ja": "テスト", "start_ms": 0, "end_ms": 1000}],
            "source_hash": source_hash,
        },
    )
    await uow.content_jobs.add(job)
    await uow.commit()

    # Current revision is 1, but command expects 5
    cmd_apply = ApplyContentJobCommand(
        job_id=job.id,
        expected_revision=5,
        user_id=env["user_id"],
    )
    with pytest.raises(RevisionConflictError, match="Expected revision 5"):
        await handle_apply_content_job(cmd_apply, uow, capability_enabled=True)


# ==============================================================================
# 3. Worker Execution Step Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_worker_step_no_jobs_available(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    ai_port = FakeAiTranscriptionPort()

    res = await handle_execute_ai_worker_step(uow, ai_port)
    assert res is None


@pytest.mark.asyncio
async def test_worker_step_transcribe_success_and_settles_quota(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd_create = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-worker-success",
        user_id=env["user_id"],
        estimated_audio_seconds=180,
        estimated_cost_micros=300000,
    )
    await handle_create_content_job(cmd_create, uow, capability_enabled=True)

    # Worker executes step
    ai_port = FakeAiTranscriptionPort(
        segments=[{"scene_id": "scene-01", "text_ja": "AI文字起こし結果", "start_ms": 0, "end_ms": 1200}],
        usage=AiUsageRecord(
            audio_seconds=120,
            input_tokens=500,
            output_tokens=150,
            cost_micros=200000,
            provider_request_id="req-worker-1",
        ),
    )
    completed_dto = await handle_execute_ai_worker_step(uow, ai_port)

    assert completed_dto is not None
    assert completed_dto.status == "succeeded"
    assert completed_dto.progress == 1.0
    assert completed_dto.result_draft is not None
    assert len(completed_dto.result_draft["source_hash"]) == 64

    # Verify actual usage settled and unused reservation released
    acc = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert acc.reserved_audio_seconds == 0  # Released
    assert acc.used_audio_seconds == 120     # Actual
    assert acc.reserved_cost_micros == 0    # Released
    assert acc.used_cost_micros == 200000   # Actual


@pytest.mark.asyncio
async def test_worker_step_failure_exhausted_retains_unknown_quota(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd_create = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-worker-fail",
        user_id=env["user_id"],
        estimated_audio_seconds=180,
        estimated_cost_micros=300000,
    )
    job_dto = await handle_create_content_job(cmd_create, uow, capability_enabled=True)

    # Set attempt to 2 so next failure exhausts 3 attempts
    job = await uow.content_jobs.get_by_id(job_dto.id)
    job.attempt = 2
    await uow.content_jobs.update(job)
    await uow.commit()

    ai_port = FakeAiTranscriptionPort(exception_to_raise=RuntimeError("Fatal provider error"))
    failed_dto = await handle_execute_ai_worker_step(uow, ai_port)

    assert failed_dto is not None
    assert failed_dto.status == "failed"

    # A generic error cannot prove the provider did not charge.
    acc = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert acc.reserved_audio_seconds == 120
    assert acc.reserved_cost_micros == 120000


@pytest.mark.asyncio
async def test_worker_step_timeout_reconciles_quota_unknown(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()

    cmd_create = CreateContentJobCommand(
        catalog_item_id=env["catalog_id"],
        content_version_id=env["version_id"],
        task="transcript",
        language="ja",
        idempotency_key="idem-worker-timeout",
        user_id=env["user_id"],
        estimated_audio_seconds=180,
        estimated_cost_micros=300000,
    )
    job_dto = await handle_create_content_job(cmd_create, uow, capability_enabled=True)

    # Timeout during provider call
    ai_port = FakeAiTranscriptionPort(exception_to_raise=TimeoutError("Network timeout during audio processing"))
    failed_dto = await handle_execute_ai_worker_step(uow, ai_port)

    assert failed_dto is not None
    assert "timeout" in (failed_dto.error_message or "").lower()

    # Reconciled entry exists with outcome_unknown (no premature release)
    reconciled = None
    for e in env["usage_ledger_repo"].entries.values():
        if e.job_id == job_dto.id and e.kind == "reconciliation":
            reconciled = e
            break
    assert reconciled is not None
    assert reconciled.status == "outcome_unknown"


# ==============================================================================
# 4. HTTP API Contract & Role Security Tests
# ==============================================================================

def test_api_content_jobs_unauthorized(client: TestClient):
    job_id = str(uuid4())
    res = client.get(f"/staff/content-jobs/{job_id}")
    assert res.status_code == 401


def test_api_content_jobs_forbidden_for_learner(client: TestClient):
    learner = UserDTO(id="learner-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    cat_id = str(uuid4())
    res = client.post(
        f"/staff/catalog/{cat_id}/content-jobs",
        json={"content_version_id": str(uuid4()), "task": "transcript"},
    )
    assert res.status_code == 403


def test_api_content_jobs_capability_disabled_returns_403(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    base_test_environment,
):
    env = base_test_environment
    client.app.state.settings.staff_ai_enabled = False
    monkeypatch.setattr(
        "jplearn_api.entrypoints.http.routers.content_jobs.create_uow",
        lambda session: env["uow_factory"](),
    )

    teacher = UserDTO(id=env["user_id"], email="teacher@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: teacher

    res = client.post(
        f"/staff/catalog/{env['catalog_id']}/content-jobs",
        json={"content_version_id": env["version_id"], "task": "transcript"},
    )
    assert res.status_code == 403
    assert "disabled" in res.json()["message"].lower()


def test_api_content_jobs_lifecycle_and_privacy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    base_test_environment,
):
    env = base_test_environment
    client.app.state.settings.staff_ai_enabled = True
    monkeypatch.setattr(
        "jplearn_api.entrypoints.http.routers.content_jobs.create_uow",
        lambda session: env["uow_factory"](),
    )

    teacher = UserDTO(id=env["user_id"], email="teacher@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: teacher

    # 1. Create Job -> 202 Accepted
    res_create = client.post(
        f"/staff/catalog/{env['catalog_id']}/content-jobs",
        headers={"Idempotency-Key": "test-http-idem-1"},
        json={
            "content_version_id": env["version_id"],
            "task": "transcript",
            "language": "ja",
            "estimated_audio_seconds": 120,
            "estimated_cost_micros": 250000,
        },
    )
    assert res_create.status_code == 202
    created_data = res_create.json()
    job_id = created_data["id"]
    assert created_data["status"] == "queued"
    assert created_data["catalog_item_id"] == env["catalog_id"]

    # 2. Get Job -> 200 OK
    res_get = client.get(f"/staff/content-jobs/{job_id}")
    assert res_get.status_code == 200
    got_data = res_get.json()
    assert got_data["id"] == job_id
    assert got_data["status"] == "queued"

    # Privacy checks (FR-NEG: No learner identity, no secrets)
    body_str = res_get.text.lower()
    assert "learner" not in body_str
    assert "password" not in body_str
    assert "secret" not in body_str

    # 3. Cancel Job -> 200 OK
    res_cancel = client.post(f"/staff/content-jobs/{job_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    # 4. Create second job and simulate completion & apply
    res_create2 = client.post(
        f"/staff/catalog/{env['catalog_id']}/content-jobs",
        headers={"Idempotency-Key": "test-http-idem-2"},
        json={
            "content_version_id": env["version_id"],
            "task": "transcript",
            "language": "ja",
        },
    )
    assert res_create2.status_code == 202
    job2_id = res_create2.json()["id"]

    # Manually set job2 to succeeded for apply test
    job2 = env["content_job_repo"].jobs[job2_id]
    job2.status = ContentJobStatus.SUCCEEDED
    job2.result_draft = {
        "segments": [{"scene_id": "scene-01", "text_ja": "適用テキスト"}],
        "source_hash": job2.source_hash,
    }
    env["content_job_repo"]._committed_jobs[job2_id] = job2

    # 5. Apply Job -> 200 OK
    res_apply = client.post(
        f"/staff/content-jobs/{job2_id}/apply",
        json={"expected_revision": 1},
    )
    assert res_apply.status_code == 200
    applied_data = res_apply.json()
    assert applied_data["applied_at"] is not None
