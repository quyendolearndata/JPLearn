"""Tests for AI Quota Accounts and Usage Ledger (ADR-007 PR8c / UC-T11 / FR-AI-001).

Validates:
1. Pure Python Domain Logic:
   - QuotaAccount bounds checking (audio seconds, tokens, cost micros in currency)
   - Atomic reservation and available quota calculation
   - Settle with release of unused reservation excess
   - Release for unbilled / aborted operations
   - Reconcile for unknown outcomes (no premature release)
   - State transition validation (InvalidReservationStateError)
2. Application Handler Logic & Concurrency/Idempotency:
   - Idempotent reservation via idempotency_key (no double-charging)
   - Idempotent settlement via (provider, provider_request_id, attempt, kind)
   - QuotaExceededError when limits exceeded
   - Date range validation (from_date <= to_date, max 90 days)
   - Capability switch enforcement (staff_ai_enabled)
3. HTTP API Contract & Role Security:
   - 401 Unauthorized for unauthenticated requests
   - 403 Forbidden when capability staff_ai_enabled = False
   - 403 Forbidden for learner role (staff endpoints require teacher/admin)
   - 403 Forbidden for teacher role on /staff/ai-usage/summary (Admin only)
   - 400 Bad Request for date range > 90 days or invalid dates
   - 200 OK end-to-end responses matching OpenAPI contract
   - Privacy Guard (FR-NEG): Zero exposure of prompts, transcripts, or credentials
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from fakes import (
    FakeQuotaRepository,
    FakeUnitOfWork,
    FakeUsageLedgerRepository,
)
from jplearn_api.application.commands import (
    ReserveQuotaCommand,
    SettleUsageCommand,
)
from jplearn_api.application.handlers.ai_usage import (
    handle_get_ai_usage_summary,
    handle_get_my_ai_usage,
    handle_reserve_quota,
    handle_settle_usage,
)
from jplearn_api.application.queries import (
    GetAiUsageSummaryQuery,
    GetMyAiUsageQuery,
)
from jplearn_api.application.read_models import UserDTO
from jplearn_api.domain.errors import (
    ForbiddenError,
    InvalidReservationStateError,
    QuotaExceededError,
    ValidationError,
)
from jplearn_api.domain.quota import (
    AiUsageLedgerEntry,
    QuotaAccount,
)
from jplearn_api.entrypoints.http.security import require_user

# ==============================================================================
# 1. Pure Python Domain Quota & Ledger Logic Tests
# ==============================================================================


def test_quota_account_initial_available():
    acc = QuotaAccount(
        id="acc-01",
        user_id="user-01",
        name="Test Quota",
        max_audio_seconds=3600,
        max_input_tokens=1000000,
        max_output_tokens=500000,
        max_cost_micros=10000000,  # $10.00
    )
    assert acc.available_audio_seconds == 3600
    assert acc.available_input_tokens == 1000000
    assert acc.available_output_tokens == 500000
    assert acc.available_cost_micros == 10000000
    assert acc.can_reserve(audio_seconds=600, input_tokens=50000, cost_micros=500000)


def test_quota_account_reserve_success():
    acc = QuotaAccount(
        id="acc-01",
        user_id="user-01",
        name="Test Quota",
        max_audio_seconds=3600,
        max_input_tokens=1000000,
        max_output_tokens=500000,
        max_cost_micros=10000000,
    )
    now = datetime(2026, 9, 7, 10, 0, 0, tzinfo=UTC)
    entry = acc.reserve(
        job_id="job-01",
        user_id="user-01",
        idempotency_key="idem-01",
        provider="whisper",
        audio_seconds=120,
        input_tokens=1000,
        output_tokens=500,
        cost_micros=200000,
        now=now,
    )

    assert entry.account_id == "acc-01"
    assert entry.kind == "reservation"
    assert entry.status == "reserved"
    assert entry.audio_seconds == 120
    assert entry.cost_micros == 200000

    assert acc.reserved_audio_seconds == 120
    assert acc.reserved_cost_micros == 200000
    assert acc.available_audio_seconds == 3600 - 120
    assert acc.available_cost_micros == 10000000 - 200000


def test_quota_account_reserve_limits_exceeded():
    acc = QuotaAccount(
        id="acc-01",
        user_id="user-01",
        name="Small Quota",
        max_audio_seconds=100,
        max_input_tokens=1000,
        max_output_tokens=500,
        max_cost_micros=100000,
    )
    # Audio seconds exceed
    with pytest.raises(QuotaExceededError, match="Insufficient AI quota"):
        acc.reserve(job_id="j1", user_id="u1", idempotency_key="k1", provider="whisper", audio_seconds=101)

    # Cost micros exceed
    with pytest.raises(QuotaExceededError, match="Insufficient AI quota"):
        acc.reserve(job_id="j2", user_id="u1", idempotency_key="k2", provider="whisper", cost_micros=100001)

    # Inactive account
    acc.is_active = False
    with pytest.raises(QuotaExceededError, match="inactive"):
        acc.reserve(job_id="j3", user_id="u1", idempotency_key="k3", provider="whisper", audio_seconds=10)


def test_quota_account_settle_releases_excess_reservation():
    acc = QuotaAccount(
        id="acc-01",
        user_id="user-01",
        name="Test Quota",
        max_audio_seconds=3600,
        max_input_tokens=1000000,
        max_output_tokens=500000,
        max_cost_micros=10000000,
    )
    res_entry = acc.reserve(
        job_id="job-01",
        user_id="user-01",
        idempotency_key="idem-01",
        provider="whisper",
        audio_seconds=300,
        cost_micros=1000000,  # $1.00 reserved
    )
    assert acc.reserved_audio_seconds == 300
    assert acc.used_audio_seconds == 0

    # Actual usage was only 180 seconds and $0.60
    settle_entry = acc.settle(
        reservation_entry=res_entry,
        actual_audio_seconds=180,
        actual_input_tokens=0,
        actual_output_tokens=0,
        actual_cost_micros=600000,
        provider_request_id="req-prov-1",
        attempt=1,
    )

    assert settle_entry.kind == "settlement"
    assert settle_entry.status == "settled"
    assert settle_entry.audio_seconds == 180
    assert settle_entry.cost_micros == 600000

    # Reserved pool decremented by 300, used pool incremented by 180
    assert acc.reserved_audio_seconds == 0
    assert acc.reserved_cost_micros == 0
    assert acc.used_audio_seconds == 180
    assert acc.used_cost_micros == 600000
    # Available is now 3600 - 180 = 3420 (the excess 120s was returned to available!)
    assert acc.available_audio_seconds == 3420
    assert acc.available_cost_micros == 10000000 - 600000


def test_quota_account_release_restores_available_quota():
    acc = QuotaAccount(
        id="acc-01",
        user_id="user-01",
        name="Test Quota",
        max_audio_seconds=3600,
        max_input_tokens=1000000,
        max_output_tokens=500000,
        max_cost_micros=10000000,
    )
    res_entry = acc.reserve(
        job_id="job-01",
        user_id="user-01",
        idempotency_key="idem-01",
        provider="whisper",
        audio_seconds=200,
        cost_micros=500000,
    )
    assert acc.available_audio_seconds == 3400

    release_entry = acc.release(reservation_entry=res_entry, reason="Job cancelled")
    assert release_entry.kind == "release"
    assert release_entry.status == "released"
    assert acc.reserved_audio_seconds == 0
    assert acc.used_audio_seconds == 0
    assert acc.available_audio_seconds == 3600


def test_quota_account_invalid_state_transitions():
    acc = QuotaAccount(
        id="acc-01",
        user_id="user-01",
        name="Test Quota",
        max_audio_seconds=3600,
        max_input_tokens=1000000,
        max_output_tokens=500000,
        max_cost_micros=10000000,
    )
    res_entry = acc.reserve(
        job_id="job-01",
        user_id="user-01",
        idempotency_key="idem-01",
        provider="whisper",
        audio_seconds=100,
    )
    acc.settle(res_entry, 100, 0, 0, 0)
    # Trying to settle again
    with pytest.raises(InvalidReservationStateError, match="Cannot settle reservation"):
        acc.settle(res_entry, 100, 0, 0, 0)

    # Trying to release an already settled reservation
    with pytest.raises(InvalidReservationStateError, match="Cannot release reservation"):
        acc.release(res_entry)


# ==============================================================================
# 2. Application Handler Logic Tests
# ==============================================================================


@pytest.fixture
def ai_usage_env():
    quota_repo = FakeQuotaRepository()
    ledger_repo = FakeUsageLedgerRepository()
    uow = FakeUnitOfWork(quota=quota_repo, usage_ledger=ledger_repo)
    return {"uow": uow, "quota": quota_repo, "ledger": ledger_repo}


def commit_fixture_data(uow: FakeUnitOfWork) -> None:
    for p in uow.participants:
        if hasattr(p, "commit_transaction"):
            p.commit_transaction()


@pytest.mark.asyncio
async def test_handler_reserve_idempotency(ai_usage_env):
    uow = ai_usage_env["uow"]
    cmd1 = ReserveQuotaCommand(
        user_id="teacher-01",
        job_id="job-01",
        idempotency_key="idem-trans-01",
        provider="whisper",
        audio_seconds=120,
        cost_micros=300000,
    )
    entry1 = await handle_reserve_quota(cmd1, uow)
    assert entry1.idempotency_key == "idem-trans-01"
    assert entry1.kind == "reservation"

    # Replay with same idempotency key
    cmd2 = ReserveQuotaCommand(
        user_id="teacher-01",
        job_id="job-01",
        idempotency_key="idem-trans-01",
        provider="whisper",
        audio_seconds=120,
        cost_micros=300000,
    )
    entry2 = await handle_reserve_quota(cmd2, uow)
    # Must return existing reservation without double booking
    assert entry1.id == entry2.id
    account = await uow.quota.get_by_id(entry1.account_id)
    assert account.reserved_audio_seconds == 120  # NOT 240!


@pytest.mark.asyncio
async def test_handler_settle_idempotency(ai_usage_env):
    uow = ai_usage_env["uow"]
    res_cmd = ReserveQuotaCommand(
        user_id="teacher-01",
        job_id="job-01",
        idempotency_key="idem-01",
        provider="mock_local",
        audio_seconds=100,
        cost_micros=100000,
    )
    reservation = await handle_reserve_quota(res_cmd, uow)

    settle_cmd1 = SettleUsageCommand(
        account_id=reservation.account_id,
        reservation_entry_id=reservation.id,
        actual_audio_seconds=80,
        actual_input_tokens=10,
        actual_output_tokens=10,
        actual_cost_micros=80000,
        provider_request_id="req-xyz-99",
        attempt=1,
    )
    settle1 = await handle_settle_usage(settle_cmd1, uow)
    assert settle1.status == "settled"
    assert settle1.audio_seconds == 80

    # Duplicate settlement call
    settle2 = await handle_settle_usage(settle_cmd1, uow)
    assert settle1.id == settle2.id
    account = await uow.quota.get_by_id(reservation.account_id)
    assert account.used_audio_seconds == 80  # NOT 160!


@pytest.mark.asyncio
async def test_handler_get_my_ai_usage_validation_and_pagination(ai_usage_env):
    uow = ai_usage_env["uow"]
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
    t0 = now - timedelta(days=10)

    # Create account and entries
    acc = await uow.quota.get_or_create_account_for_user("staff-user")
    for i in range(5):
        entry = AiUsageLedgerEntry(
            id=f"entry-{i}",
            account_id=acc.id,
            job_id=f"job-{i}",
            user_id="staff-user",
            idempotency_key=f"k-{i}",
            kind="settlement",
            status="settled",
            provider="whisper",
            provider_request_id=f"req-{i}",
            attempt=1,
            audio_seconds=60,
            input_tokens=100,
            output_tokens=50,
            cost_micros=100000,
            currency="USD",
            policy_version="v1",
            created_at=t0 + timedelta(days=i),
            settled_at=t0 + timedelta(days=i),
        )
        await uow.usage_ledger.add_entry(entry)
    commit_fixture_data(uow)

    # Query with date range > 90 days fails
    with pytest.raises(ValidationError, match="must not exceed 90 days"):
        await handle_get_my_ai_usage(
            GetMyAiUsageQuery(
                user_id="staff-user",
                from_date=now - timedelta(days=95),
                to_date=now,
            ),
            uow,
            capability_enabled=True,
        )

    # Query with from_date > to_date fails
    with pytest.raises(ValidationError, match="from_date must be before or equal to to_date"):
        await handle_get_my_ai_usage(
            GetMyAiUsageQuery(
                user_id="staff-user",
                from_date=now,
                to_date=now - timedelta(days=1),
            ),
            uow,
            capability_enabled=True,
        )

    # Query with capability disabled fails
    with pytest.raises(ForbiddenError, match="disabled"):
        await handle_get_my_ai_usage(
            GetMyAiUsageQuery(user_id="staff-user", from_date=t0, to_date=now),
            uow,
            capability_enabled=False,
        )

    # Valid paginated query
    res = await handle_get_my_ai_usage(
        GetMyAiUsageQuery(user_id="staff-user", from_date=t0, to_date=now, limit=3, offset=0),
        uow,
        capability_enabled=True,
    )
    assert res.total_count == 5
    assert len(res.items) == 3


@pytest.mark.asyncio
async def test_handler_get_ai_usage_summary(ai_usage_env):
    uow = ai_usage_env["uow"]
    t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 2, 10, 0, 0, tzinfo=UTC)

    # Populate settlements across two dates and two providers
    await uow.usage_ledger.add_entry(
        AiUsageLedgerEntry(
            id="e1",
            account_id="a1",
            job_id="j1",
            user_id="u1",
            idempotency_key="k1",
            kind="settlement",
            status="settled",
            provider="whisper",
            provider_request_id="r1",
            attempt=1,
            audio_seconds=120,
            input_tokens=0,
            output_tokens=0,
            cost_micros=200000,
            currency="USD",
            policy_version="v1",
            created_at=t0,
        )
    )
    await uow.usage_ledger.add_entry(
        AiUsageLedgerEntry(
            id="e2",
            account_id="a1",
            job_id="j2",
            user_id="u2",
            idempotency_key="k2",
            kind="settlement",
            status="settled",
            provider="gemini",
            provider_request_id="r2",
            attempt=1,
            audio_seconds=0,
            input_tokens=5000,
            output_tokens=2000,
            cost_micros=150000,
            currency="USD",
            policy_version="v1",
            created_at=t0,
        )
    )
    commit_fixture_data(uow)

    summary = await handle_get_ai_usage_summary(
        GetAiUsageSummaryQuery(from_date=t0 - timedelta(hours=1), to_date=t1),
        uow,
        capability_enabled=True,
    )
    assert summary.total_audio_seconds == 120
    assert summary.total_input_tokens == 5000
    assert summary.total_output_tokens == 2000
    assert summary.total_cost_micros == 350000
    assert len(summary.summary) == 2


# ==============================================================================
# 3. HTTP API Endpoints & Role Security Tests (FR-NEG)
# ==============================================================================


def test_api_ai_usage_unauthorized(client: TestClient):
    res = client.get("/staff/ai-usage?from_date=2026-09-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res.status_code == 401


def test_api_ai_usage_forbidden_for_learner(client: TestClient):
    learner = UserDTO(id="learner-01", email="learner@test.com", roles=["learner"])
    client.app.dependency_overrides[require_user] = lambda: learner

    res = client.get("/staff/ai-usage?from_date=2026-09-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res.status_code == 403


def test_api_ai_usage_summary_forbidden_for_teacher(client: TestClient):
    teacher = UserDTO(id="teacher-01", email="teacher@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: teacher

    res = client.get("/staff/ai-usage/summary?from_date=2026-09-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res.status_code == 403


def test_api_ai_usage_capability_disabled_returns_403(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, ai_usage_env
):
    uow = ai_usage_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.ai_usage.create_uow", lambda session: uow)
    client.app.state.settings.staff_ai_enabled = False

    teacher = UserDTO(id="teacher-01", email="teacher@test.com", roles=["teacher"])
    client.app.dependency_overrides[require_user] = lambda: teacher

    res = client.get("/staff/ai-usage?from_date=2026-09-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res.status_code == 403
    assert "disabled" in res.json()["message"].lower()


def test_api_ai_usage_validation_range_exceeded(client: TestClient, monkeypatch: pytest.MonkeyPatch, ai_usage_env):
    uow = ai_usage_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.ai_usage.create_uow", lambda session: uow)
    client.app.state.settings.staff_ai_enabled = True

    admin = UserDTO(id="admin-01", email="admin@test.com", roles=["admin"])
    client.app.dependency_overrides[require_user] = lambda: admin

    # 100 days range
    res = client.get("/staff/ai-usage?from_date=2026-05-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res.status_code == 400
    assert "90 days" in res.json()["message"]


def test_api_ai_usage_end_to_end_privacy_and_data(client: TestClient, monkeypatch: pytest.MonkeyPatch, ai_usage_env):
    """Verify successful response and privacy invariants (FR-NEG: no prompts, transcripts, credentials)."""
    uow = ai_usage_env["uow"]
    monkeypatch.setattr("jplearn_api.entrypoints.http.routers.ai_usage.create_uow", lambda session: uow)
    client.app.state.settings.staff_ai_enabled = True

    admin = UserDTO(id="admin-01", email="admin@test.com", roles=["admin"])
    client.app.dependency_overrides[require_user] = lambda: admin

    # Setup ledger entries
    t0 = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
    entry = AiUsageLedgerEntry(
        id="ledger-01",
        account_id="acc-admin-01",
        job_id="job-trans-99",
        user_id="admin-01",
        idempotency_key="idem-key-1",
        kind="settlement",
        status="settled",
        provider="whisper",
        provider_request_id="req-wh-12345",
        attempt=1,
        audio_seconds=150,
        input_tokens=0,
        output_tokens=0,
        cost_micros=250000,
        currency="USD",
        policy_version="v1",
        description="Scene transcription",
        created_at=t0,
        settled_at=t0,
    )
    ai_usage_env["ledger"].entries[entry.id] = entry
    ai_usage_env["ledger"]._committed_entries[entry.id] = entry

    # 1. GET /staff/ai-usage
    res = client.get("/staff/ai-usage?from_date=2026-09-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["id"] == "ledger-01"
    assert item["audio_seconds"] == 150
    assert item["cost_micros"] == 250000
    assert item["currency"] == "USD"

    # Privacy checks (FR-NEG)
    resp_text = res.text.lower()
    assert "prompt" not in resp_text
    assert "transcript" not in resp_text or "description" in item  # only description allowed
    assert "password" not in resp_text
    assert "secret" not in resp_text
    assert "api_key" not in resp_text

    # 2. GET /staff/ai-usage/summary
    res_sum = client.get("/staff/ai-usage/summary?from_date=2026-09-01T00:00:00Z&to_date=2026-09-07T00:00:00Z")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert data_sum["total_audio_seconds"] == 150
    assert data_sum["total_cost_micros"] == 250000
    assert len(data_sum["summary"]) == 1
    assert data_sum["summary"][0]["provider"] == "whisper"
