"""Fault tests for worker admission and late provider accounting; no network/DB."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from fakes import FakeAiTranscriptionPort
from jplearn_api.adapters.persistence.content_job_repository import SqlAlchemyContentJobRepository
from jplearn_api.adapters.persistence.quota_repository import SqlAlchemyUsageLedgerRepository
from jplearn_api.application.commands import ApplyContentJobCommand, CancelContentJobCommand, CreateContentJobCommand
from jplearn_api.application.handlers.ai_attempts import reconcile_ai_attempt, sweep_expired_ai_attempts
from jplearn_api.application.handlers.content_jobs import (
    handle_apply_content_job,
    handle_cancel_content_job,
    handle_create_content_job,
    handle_execute_ai_worker_step,
)
from jplearn_api.domain.ai_attempt import AiAttempt
from jplearn_api.domain.content_job import ContentJobStatus
from jplearn_api.domain.errors import ConflictError
from jplearn_api.domain.quota import QuotaAccount
from jplearn_api.entrypoints.cli import ai_worker
from test_content_jobs import base_test_environment as base_test_environment


@pytest.mark.asyncio
async def test_disabled_worker_does_not_open_database(monkeypatch):
    monkeypatch.setattr(ai_worker, "get_settings", lambda: SimpleNamespace(staff_ai_enabled=False))
    monkeypatch.setattr(ai_worker, "create_engine_and_sessions", lambda _: pytest.fail("DB opened"))
    assert await ai_worker.run_ai_worker(once=True) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("environment,trial", [("production", True), ("staging", True), ("local", False)])
async def test_missing_provider_fails_before_claim(monkeypatch, environment, trial):
    monkeypatch.setattr(
        ai_worker,
        "get_settings",
        lambda: SimpleNamespace(
            staff_ai_enabled=True,
            environment=environment,
            enable_trial_transcriber=trial,
        ),
    )
    monkeypatch.setattr(ai_worker, "create_engine_and_sessions", lambda _: pytest.fail("DB opened"))
    with pytest.raises(RuntimeError, match="No jobs were claimed"):
        await ai_worker.run_ai_worker(once=True)


@pytest.mark.asyncio
async def test_disabled_step_does_not_claim():
    uow = SimpleNamespace(content_jobs=SimpleNamespace(claim_next_queued_job=AsyncMock()))
    assert await handle_execute_ai_worker_step(uow, FakeAiTranscriptionPort(), capability_enabled=False) is None
    uow.content_jobs.claim_next_queued_job.assert_not_called()


@pytest.mark.asyncio
async def test_persistence_claim_only_selects_queued():
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)))
    await SqlAlchemyContentJobRepository(session).claim_next_queued_job(datetime.now(UTC), 60, "token")
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(compile_kwargs={"literal_binds": True})
    assert "status = 'queued'" in str(compiled)
    assert "status = 'running'" not in str(compiled)
    assert "attempt < content_jobs.max_attempts" in str(compiled)


@pytest.mark.asyncio
async def test_cancel_during_provider_success_still_records_cost(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    job = await handle_create_content_job(
        CreateContentJobCommand(
            catalog_item_id=env["catalog_id"],
            content_version_id=env["version_id"],
            task="transcript",
            language="ja",
            idempotency_key="late-cost",
            user_id=env["user_id"],
            estimated_audio_seconds=120,
            estimated_cost_micros=300000,
        ),
        uow,
    )

    class CancelDuringCall(FakeAiTranscriptionPort):
        async def transcribe_and_segment(self, **kwargs):
            await handle_cancel_content_job(
                CancelContentJobCommand(
                    job_id=job.id,
                    user_id=env["user_id"],
                    user_roles=("teacher",),
                ),
                uow,
            )
            return await super().transcribe_and_segment(**kwargs)

    assert await handle_execute_ai_worker_step(uow, CancelDuringCall()) is None
    persisted_job = await uow.content_jobs.get_by_id(job.id)
    assert persisted_job.status.value == "cancelled"
    entries = list(env["usage_ledger_repo"].entries.values())
    settlements = [entry for entry in entries if entry.kind == "settlement"]
    assert len(settlements) == 1
    assert settlements[0].attempt == 1
    assert settlements[0].cost_micros > 0


@pytest.mark.asyncio
async def test_cancel_then_timeout_keeps_unknown_reservation(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    job = await handle_create_content_job(
        CreateContentJobCommand(
            catalog_item_id=env["catalog_id"],
            content_version_id=env["version_id"],
            task="transcript",
            language="ja",
            idempotency_key="cancel-timeout",
            user_id=env["user_id"],
            estimated_audio_seconds=120,
            estimated_cost_micros=300000,
        ),
        uow,
    )

    class TimeoutAfterCancel(FakeAiTranscriptionPort):
        async def transcribe_and_segment(self, **kwargs):
            await handle_cancel_content_job(
                CancelContentJobCommand(
                    job_id=job.id,
                    user_id=env["user_id"],
                    user_roles=("teacher",),
                ),
                uow,
            )
            raise TimeoutError("provider may already have billed")

    assert await handle_execute_ai_worker_step(uow, TimeoutAfterCancel()) is None
    entries = list(env["usage_ledger_repo"].entries.values())
    unknown = [entry for entry in entries if entry.kind == "reconciliation"]
    assert len(unknown) == 1
    assert unknown[0].status == "outcome_unknown"
    assert not any(entry.kind == "release" for entry in entries)
    account = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert account.reserved_cost_micros == 120000


@pytest.mark.asyncio
async def test_outcome_updates_detached_reservation_model():
    account = QuotaAccount("a", "u", "test", 1000, 1000, 1000, 1000)
    reservation = account.reserve("j", "u", "key", "test", cost_micros=100)
    account.reconcile(reservation, "outcome_unknown")
    entry = account.settle(reservation, 10, 1, 1, 25, provider_request_id="request-1")
    model = SimpleNamespace(status="outcome_unknown", settled_at=None)
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: model)),
        add=lambda entry: None,
        flush=AsyncMock(),
    )
    await SqlAlchemyUsageLedgerRepository(session).add_entry(entry)
    assert model.status == "settled"
    assert model.settled_at is not None
    assert account.used_cost_micros == 25


@pytest.mark.asyncio
async def test_apply_failure_rolls_back_transcript_and_job(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    dto = await handle_create_content_job(
        CreateContentJobCommand(
            catalog_item_id=env["catalog_id"],
            content_version_id=env["version_id"],
            task="transcript",
            language="ja",
            idempotency_key="atomic-apply",
            user_id=env["user_id"],
            estimated_audio_seconds=120,
            estimated_cost_micros=300000,
        ),
        uow,
    )
    async with uow:
        job = await uow.content_jobs.get_by_id(dto.id)
        job.status = ContentJobStatus.SUCCEEDED
        job.result_draft = {"segments": [{"scene_id": "scene-01", "text_ja": "変更"}]}
        await uow.content_jobs.update(job)
        await uow.commit()
    uow.content_jobs.update = AsyncMock(side_effect=RuntimeError("write failed"))
    with pytest.raises(RuntimeError, match="write failed"):
        await handle_apply_content_job(
            ApplyContentJobCommand(
                job_id=dto.id,
                expected_revision=1,
                user_id=env["user_id"],
            ),
            uow,
        )
    async with env["uow_factory"]() as reader:
        transcript = await reader.transcripts.get_latest_revision(env["catalog_id"], env["version_id"])
        assert transcript.revision == 1
        assert transcript.segments[0].text_ja == "初期テキスト"
        job = await reader.content_jobs.get_by_id(dto.id)
        assert job.applied_at is None


@pytest.mark.asyncio
async def test_unknown_attempt_can_be_reconciled_not_billed_exactly_once(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    job = await handle_create_content_job(
        CreateContentJobCommand(
            catalog_item_id=env["catalog_id"],
            content_version_id=env["version_id"],
            task="transcript",
            language="ja",
            idempotency_key="reconcile-not-billed",
            user_id=env["user_id"],
            estimated_audio_seconds=120,
            estimated_cost_micros=300000,
        ),
        uow,
    )
    await handle_execute_ai_worker_step(
        uow,
        FakeAiTranscriptionPort(exception_to_raise=TimeoutError("unknown outcome")),
        attempt_token="attempt-not-billed",
    )

    request = dict(
        job_id=job.id,
        attempt_id="attempt-not-billed",
        user_id=env["user_id"],
        user_roles=("admin",),
        decision="not_billed",
        evidence="Provider console confirms that no request was billed.",
    )
    first = await reconcile_ai_attempt(uow, **request)
    second = await reconcile_ai_attempt(uow, **request)
    assert first.state == second.state == "not_billed"
    account = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert account.reserved_cost_micros == 0
    assert len([e for e in env["usage_ledger_repo"].entries.values() if e.kind == "release"]) == 1

    with pytest.raises(ConflictError, match="already reconciled"):
        await reconcile_ai_attempt(
            uow,
            **{**request, "evidence": "Different provider evidence for the same attempt."},
        )


@pytest.mark.asyncio
async def test_unknown_attempt_can_be_reconciled_with_actual_billed_usage(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    job = await handle_create_content_job(
        CreateContentJobCommand(
            catalog_item_id=env["catalog_id"],
            content_version_id=env["version_id"],
            task="transcript",
            language="ja",
            idempotency_key="reconcile-billed",
            user_id=env["user_id"],
            estimated_audio_seconds=120,
            estimated_cost_micros=300000,
        ),
        uow,
    )
    await handle_execute_ai_worker_step(
        uow,
        FakeAiTranscriptionPort(exception_to_raise=TimeoutError("unknown outcome")),
        attempt_token="attempt-billed",
    )

    attempt = await reconcile_ai_attempt(
        uow,
        job_id=job.id,
        attempt_id="attempt-billed",
        user_id=env["user_id"],
        user_roles=("admin",),
        decision="billed",
        evidence="Provider invoice confirms this request and its measured usage.",
        provider_request_id="provider-request-recovered",
        usage={"audio_seconds": 118, "input_tokens": 90, "output_tokens": 20, "cost_micros": 125000, "currency": "USD"},
    )
    assert attempt.state == "settled"
    account = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert account.reserved_cost_micros == 0
    assert account.used_cost_micros == 125000
    settlements = [e for e in env["usage_ledger_repo"].entries.values() if e.kind == "settlement"]
    assert len(settlements) == 1
    assert settlements[0].provider_request_id == "provider-request-recovered"


@pytest.mark.asyncio
async def test_expired_attempt_is_quarantined_without_retry_or_quota_release(base_test_environment):
    env = base_test_environment
    uow = env["uow_factory"]()
    dto = await handle_create_content_job(
        CreateContentJobCommand(
            catalog_item_id=env["catalog_id"],
            content_version_id=env["version_id"],
            task="transcript",
            language="ja",
            idempotency_key="expired-attempt",
            user_id=env["user_id"],
            estimated_audio_seconds=120,
            estimated_cost_micros=300000,
        ),
        uow,
    )
    now = datetime.now(UTC)
    async with uow:
        job = await uow.content_jobs.get_by_id(dto.id)
        job.claim_lease("expired-token", now - timedelta(seconds=1), now - timedelta(seconds=61))
        await uow.content_jobs.update(job)
        await uow.content_jobs.save_attempt(
            AiAttempt(
                id="expired-token",
                job_id=job.id,
                attempt_number=job.attempt,
                provider="test",
                idempotency_key="ai-attempt:expired-token",
                state="running",
                lease_expires_at=now - timedelta(seconds=1),
                created_at=now - timedelta(seconds=61),
                updated_at=now - timedelta(seconds=61),
            )
        )
        await uow.commit()

    assert await sweep_expired_ai_attempts(uow, now=now) == 1
    attempt = await uow.content_jobs.get_attempt("expired-token")
    job = await uow.content_jobs.get_by_id(dto.id)
    account = await uow.quota.get_or_create_account_for_user(env["user_id"])
    assert attempt.state == "outcome_unknown"
    assert job.status == ContentJobStatus.FAILED
    assert job.attempt == 1
    assert account.reserved_cost_micros == 120000
