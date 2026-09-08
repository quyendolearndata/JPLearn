"""Integration concurrency tests against PostgreSQL for remediation invariants (R8 Concurrency Regression Suite).

Validates:
1. P1.2 / P2: Content version incremental numbering & CAS concurrency.
2. P1.3 / P1.7: Playback epoch fencing & idempotent receipt replay on superseded session.
3. P1.13: AI content job settlement atomicity under concurrent cancellation / provider completion.
4. P1.10: Transcript draft atomic CAS update contention.
"""

from __future__ import annotations

import asyncio
import tempfile
from uuid import uuid4

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from jplearn_api.adapters.persistence.connection import create_engine_and_sessions
from jplearn_api.application.commands import (
    CancelContentJobCommand,
    CreateContentJobCommand,
    SaveTranscriptDraftCommand,
)
from jplearn_api.application.handlers.content_jobs import (
    handle_cancel_content_job,
    handle_create_content_job,
    handle_execute_ai_worker_step,
)
from jplearn_api.application.handlers.transcript import handle_save_transcript_draft
from jplearn_api.application.ports.ai_provider import (
    AiTranscriptionPort,
    AiTranscriptionResult,
    AiUsageRecord,
)
from jplearn_api.bootstrap import create_uow
from jplearn_api.domain.catalog import CatalogItem, MediaRef
from jplearn_api.domain.content import ContentVersion, Scene
from jplearn_api.domain.errors import RevisionConflictError
from jplearn_api.domain.quota import QuotaAccount
from jplearn_api.entrypoints.cli.seed import seed_url
from jplearn_api.entrypoints.http.app import create_app, lifespan
from jplearn_api.settings import Settings
from pg_harness import start_docker_postgres, stop_docker_postgres


@pytest.fixture(scope="module")
def postgres_url() -> str:
    import os

    project = f"jplearn-pytest-{os.getpid()}-remediation"
    stop_docker_postgres(project)
    url = start_docker_postgres(project)
    try:
        yield url
    finally:
        stop_docker_postgres(project)


@pytest.fixture
async def client_factory(postgres_url: str):
    await seed_url(postgres_url)
    with tempfile.TemporaryDirectory() as storage_root:
        settings = Settings(
            database_url=postgres_url,
            jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
            api_public_url="http://localhost:8000",
            environment="test",
            storage_root=storage_root,
            openapi_ui=False,
            video_scene_breakdown_enabled=True,
            smart_stream_enabled=True,
            interactive_dual_subs_enabled=True,
            immersion_lookup_enabled=True,
            personal_collections_enabled=True,
            content_reports_enabled=True,
            playback_tracking_enabled=True,
            scene_search_enabled=True,
            staff_ai_enabled=True,
            enable_trial_transcriber=True,
        )
        app = create_app(settings)
        async with lifespan(app):

            async def _make_client():
                transport = ASGITransport(app=app)
                return AsyncClient(transport=transport, base_url="http://test")

            yield _make_client


async def _create_user_with_roles(client: AsyncClient, postgres_url: str, roles: list[str]) -> tuple[str, str]:
    email = f"user_{uuid4().hex[:8]}@example.com"
    res = await client.post("/auth/register", json={"email": email, "password": "password10"})
    assert res.status_code == 201, res.text
    user_id = res.json()["user"]["id"]
    token = res.json()["access_token"]

    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        for role in roles:
            await conn.execute(
                'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
                user_id,
                role,
            )
    finally:
        await conn.close()

    return user_id, token


# ==============================================================================
# 1. Content Version Incremental Numbering & CAS Concurrency (P1.2, P2)
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrent_content_draft_update_cas_contention(client_factory, postgres_url: str):
    """Two concurrent PUT /staff/catalog/{id}/content with same expected_version_number.

    Exactly one must succeed (200), and the other must be rejected with 409 Conflict.
    """
    make_client = client_factory
    client = await make_client()
    _, token = await _create_user_with_roles(client, postgres_url, ["admin", "teacher"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a draft catalog item
    create_res = await client.post(
        "/staff/catalog",
        headers=headers,
        json={
            "topic_id": "daily_home",
            "ci_level": 0,
            "duration_seconds": 30,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "content-cas-test",
        },
    )
    assert create_res.status_code == 201, create_res.text
    item_id = create_res.json()["id"]

    # 2. Get initial content draft to discover expected_version_number
    get_res = await client.get(f"/staff/catalog/{item_id}/content", headers=headers)
    assert get_res.status_code == 200, get_res.text
    expected_rev = get_res.json().get("revision", 1)

    payload_a = {
        "version_revision": expected_rev,
        "scenes": [
            {
                "scene_index": 1,
                "start_time_seconds": 0,
                "end_time_seconds": 10,
                "title_jp": "シーンA",
                "transcript_jp": "テキストA",
            }
        ],
    }
    payload_b = {
        "version_revision": expected_rev,
        "scenes": [
            {
                "scene_index": 1,
                "start_time_seconds": 0,
                "end_time_seconds": 15,
                "title_jp": "シーンB",
                "transcript_jp": "テキストB",
            }
        ],
    }

    # 3. Fire concurrent updates with same expected_version_number
    res_a, res_b = await asyncio.gather(
        client.put(f"/staff/catalog/{item_id}/content", headers=headers, json=payload_a),
        client.put(f"/staff/catalog/{item_id}/content", headers=headers, json=payload_b),
        return_exceptions=True,
    )

    statuses = [res_a.status_code, res_b.status_code]
    assert 200 in statuses, f"Expected at least one 200, got {statuses}"
    assert 409 in statuses, f"Expected at least one 409 conflict, got {statuses}"


# ==============================================================================
# 2. Playback Epoch Fencing & Idempotent Receipt Replay (P1.3, P1.7)
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrent_playback_epoch_fencing_and_idempotent_replay(client_factory, postgres_url: str):
    """Validate playback fencing: superseded session checkpoint is fenced, but duplicate sequence is idempotent."""
    make_client = client_factory
    client = await make_client()
    _, token = await _create_user_with_roles(client, postgres_url, ["learner", "admin"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a published item
    item_res = await client.post(
        "/staff/catalog",
        headers=headers,
        json={
            "topic_id": "daily_home",
            "ci_level": 1,
            "duration_seconds": 60,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "playback-fencing-test",
        },
    )
    assert item_res.status_code == 201
    item_id = item_res.json()["id"]

    # Put content draft (creates content_version row in DB)
    await client.put(
        f"/staff/catalog/{item_id}/content",
        headers=headers,
        json={
            "version_revision": 1,
            "scenes": [
                {
                    "scene_index": 1,
                    "start_time_seconds": 0,
                    "end_time_seconds": 10,
                    "title_jp": "シーン1",
                    "transcript_jp": "テキスト1",
                }
            ],
        },
    )

    # Set status directly to published so playback can start
    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await conn.execute("UPDATE catalog_items SET status = 'published' WHERE id = $1", item_id)
        await conn.execute("UPDATE content_versions SET is_published = true WHERE catalog_item_id = $1", item_id)
    finally:
        await conn.close()

    # 2. Start session 1
    s1_res = await client.post(
        "/playbacks",
        headers=headers,
        json={"catalog_item_id": item_id, "device_id": "dev-1"},
    )
    assert s1_res.status_code == 201, s1_res.text
    session1_id = s1_res.json()["playback_id"]
    epoch1 = s1_res.json()["epoch"]

    # 3. Start session 2 (supersedes session 1 and bumps epoch)
    s2_res = await client.post(
        "/playbacks",
        headers=headers,
        json={"catalog_item_id": item_id, "device_id": "dev-2", "take_over": True},
    )
    assert s2_res.status_code == 201, s2_res.text
    session2_id = s2_res.json()["playback_id"]
    epoch2 = s2_res.json()["epoch"]
    assert epoch2 > epoch1

    # 4. Session 2 sends checkpoint sequence 1 -> success
    cp2_res = await client.put(
        f"/playbacks/{session2_id}/checkpoints/1",
        headers=headers,
        json={
            "position_ms": 10000,
            "duration_ms": 60000,
            "playback_rate": 1.0,
            "state": "playing",
            "client_cumulative_active_ms": 5000,
            "client_epoch": epoch2,
        },
    )
    assert cp2_res.status_code == 200, cp2_res.text
    ack2 = cp2_res.json()
    assert ack2["seq"] == 1
    assert ack2["accepted_delta_ms"] > 0

    # 5. Session 2 retries checkpoint sequence 1 -> idempotent ACK
    cp2_retry = await client.put(
        f"/playbacks/{session2_id}/checkpoints/1",
        headers=headers,
        json={
            "position_ms": 10000,
            "duration_ms": 60000,
            "playback_rate": 1.0,
            "state": "playing",
            "client_cumulative_active_ms": 5000,
            "client_epoch": epoch2,
        },
    )
    assert cp2_retry.status_code == 200, cp2_retry.text
    assert cp2_retry.json()["seq"] == 1

    # 6. Session 1 (superseded) attempts checkpoint -> fenced (409 Conflict)
    cp1_res = await client.put(
        f"/playbacks/{session1_id}/checkpoints/1",
        headers=headers,
        json={
            "position_ms": 5000,
            "duration_ms": 60000,
            "playback_rate": 1.0,
            "state": "playing",
            "client_cumulative_active_ms": 2000,
            "client_epoch": epoch1,
        },
    )
    assert cp1_res.status_code == 409, cp1_res.text


# ==============================================================================
# 3. AI Worker Settle vs Cancellation Contention (P1.13)
# ==============================================================================


class DelayedAiPort(AiTranscriptionPort):
    """Fake AI provider simulating a network delay while calling external API."""

    def __init__(self, entered_event: asyncio.Event | None = None, delay_seconds: float = 0.05) -> None:
        self.entered_event = entered_event
        self.delay_seconds = delay_seconds

    async def transcribe_and_segment(
        self,
        media_storage_key: str,
        media_duration_seconds: int,
        language: str = "ja",
    ) -> AiTranscriptionResult:
        if self.entered_event is not None:
            self.entered_event.set()
        await asyncio.sleep(self.delay_seconds)
        return AiTranscriptionResult(
            segments=[{"scene_id": "sc-01", "text_ja": "遅延テスト結果", "start_ms": 0, "end_ms": 2000}],
            usage=AiUsageRecord(
                audio_seconds=120,
                input_tokens=400,
                output_tokens=120,
                cost_micros=150000,
                provider_request_id="delayed-req-1",
            ),
            provenance={"provider": "delayed_transcriber", "model": "test-v1"},
        )


@pytest.mark.asyncio
async def test_ai_worker_settle_under_concurrent_cancellation(client_factory, postgres_url: str):
    """P1.13: When a running job is cancelled during an AI provider call,
    the worker settles provider spend without corrupting the draft.
    """
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        api_public_url="http://localhost:8000",
        environment="test",
        staff_ai_enabled=True,
    )
    engine, session_maker = create_engine_and_sessions(settings)

    try:
        user_id = f"teacher_{uuid4().hex[:8]}"
        catalog_id = f"cat_{uuid4().hex[:8]}"
        version_id = f"ver_{uuid4().hex[:8]}"

        # Insert user to satisfy foreign key constraint
        conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            await conn.execute(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_id,
                f"{user_id}@example.com",
                "dummy_hash",
            )
        finally:
            await conn.close()

        # Setup initial DB rows
        async with session_maker() as session:
            uow = create_uow(session)
            # Create user & quota account
            quota_acc = QuotaAccount(
                id=f"acc_{user_id}",
                user_id=user_id,
                name="Teacher Quota",
                max_audio_seconds=3600,
                max_input_tokens=1000000,
                max_output_tokens=500000,
                max_cost_micros=10000000,
            )
            await uow.quota.save_account(quota_acc)

            # Create catalog item with media
            cat_item = CatalogItem(
                id=catalog_id,
                topic_id="daily_home",
                ci_level=1,
                duration_seconds=120,
                media_type="video",
                visual_support="high",
                title_internal="AI race test item",
                created_by=user_id,
                media=[MediaRef(id=f"med_{catalog_id}", storage_key="test.mp4")],
            )
            await uow.catalog.add(cat_item)

            from jplearn_api.domain.media import MediaAsset

            await uow.media.add(
                MediaAsset(
                    id=f"med_{catalog_id}",
                    catalog_item_id=catalog_id,
                    storage_key="test.mp4",
                    mime="video/mp4",
                )
            )

            # Create content version with scene
            scene_id_3 = f"sc_{uuid4().hex[:8]}"
            version = ContentVersion(
                id=version_id,
                catalog_item_id=catalog_id,
                version_number=1,
                scenes=[
                    Scene(
                        id=scene_id_3,
                        scene_index=1,
                        start_time_seconds=0,
                        end_time_seconds=10,
                        title_jp="シーン1",
                        transcript_jp="元テキスト",
                    )
                ],
            )
            await uow.content.save_draft(version)
            await uow.commit()

        # Create AI Job
        async with session_maker() as session:
            uow = create_uow(session)
            cmd_create = CreateContentJobCommand(
                catalog_item_id=catalog_id,
                content_version_id=version_id,
                task="transcript",
                language="ja",
                idempotency_key=f"idem_{uuid4().hex[:8]}",
                user_id=user_id,
                estimated_audio_seconds=120,
                estimated_cost_micros=200000,
            )
            job_dto = await handle_create_content_job(cmd_create, uow, capability_enabled=True)
            assert job_dto.status == "queued"

        provider_started = asyncio.Event()

        # Concurrently: worker runs with delayed provider, while client cancels job
        async def _run_worker():
            async with session_maker() as session:
                uow = create_uow(session)
                return await handle_execute_ai_worker_step(
                    uow, DelayedAiPort(entered_event=provider_started, delay_seconds=0.1)
                )

        async def _cancel_job():
            await asyncio.wait_for(
                provider_started.wait(), timeout=5.0
            )  # Wait for worker to claim and enter provider call
            async with session_maker() as session:
                uow = create_uow(session)
                cmd_cancel = CancelContentJobCommand(
                    job_id=job_dto.id,
                    user_id=user_id,
                    user_roles=["teacher"],
                )
                return await handle_cancel_content_job(cmd_cancel, uow, capability_enabled=True)

        worker_res, cancel_res = await asyncio.gather(_run_worker(), _cancel_job(), return_exceptions=True)

        # Job is cancelled
        assert cancel_res.status == "cancelled"

        # Verify quota ledger: provider actual usage was settled even though job was cancelled
        async with session_maker() as session:
            uow = create_uow(session)
            acc = await uow.quota.get_or_create_account_for_user(user_id)
            assert acc.reserved_audio_seconds == 0  # Reservation cleared
            assert acc.used_audio_seconds == 120  # Settled actual usage
            assert acc.used_cost_micros == 150000  # Settled actual cost

            # Job status remains cancelled and was not overwritten to succeeded
            job = await uow.content_jobs.get_by_id(job_dto.id)
            assert job.status.value == "cancelled"
            assert job.result_draft is None or job.applied_at is None
    finally:
        await engine.dispose()


# ==============================================================================
# 4. Transcript CAS Update Contention (P1.10)
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrent_transcript_draft_atomic_cas_contention(client_factory, postgres_url: str):
    "P1.10: Under concurrent transcript updates on PostgreSQL, atomic CAS ensures exactly one update wins per revision."
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        api_public_url="http://localhost:8000",
        environment="test",
    )
    engine, session_maker = create_engine_and_sessions(settings)

    try:
        user_a = f"teacher_a_{uuid4().hex[:8]}"
        user_b = f"teacher_b_{uuid4().hex[:8]}"
        catalog_id = f"cat_{uuid4().hex[:8]}"
        version_id = f"ver_{uuid4().hex[:8]}"

        # Insert users to satisfy foreign key constraints
        conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            await conn.execute(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_a,
                f"{user_a}@example.com",
                "dummy_hash",
            )
            await conn.execute(
                "INSERT INTO users (id, email, password_hash) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                user_b,
                f"{user_b}@example.com",
                "dummy_hash",
            )
        finally:
            await conn.close()

        # 0. Setup catalog item & content version
        async with session_maker() as session:
            uow = create_uow(session)
            cat_item = CatalogItem(
                id=catalog_id,
                topic_id="daily_home",
                ci_level=1,
                duration_seconds=60,
                media_type="video",
                visual_support="high",
                title_internal="CAS transcript test item",
                created_by=user_a,
            )
            await uow.catalog.add(cat_item)
            scene_id_4 = f"sc_{uuid4().hex[:8]}"
            version = ContentVersion(
                id=version_id,
                catalog_item_id=catalog_id,
                version_number=1,
                scenes=[
                    Scene(
                        id=scene_id_4,
                        scene_index=1,
                        start_time_seconds=0,
                        end_time_seconds=10,
                        title_jp="シーン1",
                        transcript_jp="元テキスト",
                    )
                ],
            )
            await uow.content.save_draft(version)
            await uow.commit()

        # 1. Setup initial draft transcript at revision 1
        async with session_maker() as session:
            uow = create_uow(session)
            cmd_init = SaveTranscriptDraftCommand(
                catalog_item_id=catalog_id,
                content_version_id=version_id,
                expected_revision=1,
                segments=[{"scene_id": scene_id_4, "text_ja": "初期原稿"}],
                user_id=user_a,
            )
            init_rev = await handle_save_transcript_draft(cmd_init, uow)
            assert init_rev.revision == 1

        # 2. Concurrently fire two updates targeting expected_revision=1
        async def _update_a():
            async with session_maker() as session:
                uow = create_uow(session)
                cmd_a = SaveTranscriptDraftCommand(
                    catalog_item_id=catalog_id,
                    content_version_id=version_id,
                    expected_revision=1,
                    segments=[{"scene_id": scene_id_4, "text_ja": "更新テキストA"}],
                    user_id=user_a,
                )
                return await handle_save_transcript_draft(cmd_a, uow)

        async def _update_b():
            async with session_maker() as session:
                uow = create_uow(session)
                cmd_b = SaveTranscriptDraftCommand(
                    catalog_item_id=catalog_id,
                    content_version_id=version_id,
                    expected_revision=1,
                    segments=[{"scene_id": scene_id_4, "text_ja": "更新テキストB"}],
                    user_id=user_b,
                )
                return await handle_save_transcript_draft(cmd_b, uow)

        res_a, res_b = await asyncio.gather(_update_a(), _update_b(), return_exceptions=True)

        results = [res_a, res_b]
        successes = [r for r in results if not isinstance(r, Exception)]
        conflicts = [r for r in results if isinstance(r, RevisionConflictError)]

        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
        assert len(conflicts) == 1, f"Expected exactly 1 RevisionConflictError, got {len(conflicts)}: {results}"
        assert successes[0].revision == 2

        # 3. Verify in database: latest revision is 2
        async with session_maker() as session:
            uow = create_uow(session)
            latest = await uow.transcripts.get_latest_revision(catalog_id, version_id)
            assert latest is not None
            assert latest.revision == 2
    finally:
        await engine.dispose()
