"""Concurrency and race condition tests for learning session creation and idempotency.

Prevents P1 bug R-02:
Under concurrent duplicate POST /sessions with the same Idempotency-Key,
Postgres advisory transaction lock (pg_advisory_xact_lock) serializes requests,
preventing unique constraint violation 500s and ensuring idempotency replay (201)
or payload conflict (409).
"""

from __future__ import annotations

import asyncio
import tempfile
from uuid import uuid4

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from jplearn_api.entrypoints.cli.seed import seed_url
from jplearn_api.entrypoints.http.app import create_app, lifespan
from jplearn_api.settings import Settings
from pg_harness import start_docker_postgres, stop_docker_postgres


@pytest.fixture(scope="module")
def postgres_url() -> str:
    project = "jplearn-sessions-concurrency"
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
        )
        app = create_app(settings)
        async with lifespan(app):
            async def _make_client():
                transport = ASGITransport(app=app)
                return AsyncClient(transport=transport, base_url="http://test")

            yield _make_client


async def _create_learner_token(client: AsyncClient) -> tuple[str, str]:
    email = f"learner_{uuid4().hex[:8]}@example.com"
    res = await client.post("/auth/register", json={"email": email, "password": "password10"})
    assert res.status_code == 201, res.text
    user_id = res.json()["user"]["id"]
    token = res.json()["access_token"]
    return user_id, token


@pytest.mark.asyncio
async def test_concurrent_start_session_same_key_same_body(client_factory, postgres_url: str):
    """Two concurrent requests with same key and body must both succeed, returning identical session ID."""
    make_client = client_factory
    init_client = await make_client()
    user_id, token = await _create_learner_token(init_client)

    idempotency_key = f"idem-{uuid4()}"
    barrier = asyncio.Barrier(2)

    async def worker():
        c = await make_client()
        await barrier.wait()
        return await c.post(
            "/sessions",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key,
            },
            json={"device_class": "web"},
        )

    t1 = asyncio.create_task(worker())
    t2 = asyncio.create_task(worker())
    res1, res2 = await asyncio.gather(t1, t2)

    assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.text}"
    assert res2.status_code == 201, f"Expected 201, got {res2.status_code}: {res2.text}"

    body1 = res1.json()
    body2 = res2.json()
    assert body1["id"] == body2["id"], "Both requests must return the identical session ID"

    session_id = body1["id"]

    # Verify DB state directly via asyncpg: exactly 1 session, 1 idempotency key, 2 events
    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        session_count = await conn.fetchval(
            "SELECT COUNT(*) FROM learning_sessions WHERE user_id = $1", user_id
        )
        assert session_count == 1, f"Expected exactly 1 session in DB, got {session_count}"

        key_count = await conn.fetchval(
            "SELECT COUNT(*) FROM session_idempotency_keys WHERE user_id = $1 AND key = $2",
            user_id,
            idempotency_key,
        )
        assert key_count == 1, f"Expected exactly 1 idempotency key row in DB, got {key_count}"

        events = await conn.fetch(
            "SELECT type FROM learning_events WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
        assert len(events) == 2, f"Expected exactly 2 events, got {len(events)}"
        assert [e["type"] for e in events] == ["session_started", "level_exposed"]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_concurrent_start_session_same_key_different_body(client_factory, postgres_url: str):
    """Two concurrent requests with same key but different body must produce 1 winner (201) and 1 conflict (409)."""
    make_client = client_factory
    init_client = await make_client()
    user_id, token = await _create_learner_token(init_client)

    idempotency_key = f"idem-{uuid4()}"
    barrier = asyncio.Barrier(2)

    async def worker(device_class: str):
        c = await make_client()
        await barrier.wait()
        return await c.post(
            "/sessions",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": idempotency_key,
            },
            json={"device_class": device_class},
        )

    t1 = asyncio.create_task(worker("web"))
    t2 = asyncio.create_task(worker("phone"))
    res1, res2 = await asyncio.gather(t1, t2)

    statuses = {res1.status_code, res2.status_code}
    assert statuses == {201, 409}, f"Expected {201, 409}, got: {res1.status_code}, {res2.status_code}"

    # Verify DB state directly: exactly 1 session created, 0 error rows
    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        session_count = await conn.fetchval(
            "SELECT COUNT(*) FROM learning_sessions WHERE user_id = $1", user_id
        )
        assert session_count == 1, f"Expected exactly 1 session in DB, got {session_count}"
    finally:
        await conn.close()
