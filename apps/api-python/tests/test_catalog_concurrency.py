"""Tests for atomic catalog optimistic concurrency control and state transitions (T-CAT-005-CAS)."""

from __future__ import annotations

import asyncio
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from jplearn_api.entrypoints.http.app import create_app
from jplearn_api.settings import Settings
from jplearn_api.entrypoints.cli.seed import seed_url
from pg_harness import start_docker_postgres, stop_docker_postgres


from jplearn_api.entrypoints.http.app import create_app, lifespan


@pytest.fixture(scope="module")
def postgres_url() -> str:
    project = "jplearn-catalog-concurrency"
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


from uuid import uuid4
import asyncpg


async def _create_admin_token(client: AsyncClient, postgres_url: str) -> str:
    email = f"admin_{uuid4().hex[:8]}@example.com"
    res = await client.post("/auth/register", json={"email": email, "password": "password10"})
    assert res.status_code == 201, res.text
    user_id = res.json()["user"]["id"]

    conn = await asyncpg.connect(postgres_url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await conn.execute(
            'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
            user_id,
            "admin",
        )
        await conn.execute(
            'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
            user_id,
            "teacher",
        )
    finally:
        await conn.close()

    return res.json()["access_token"]


@pytest.mark.asyncio
async def test_concurrent_patch_same_revision_exactly_one_wins(client_factory, postgres_url: str):
    """Two concurrent PATCH requests on the same revision must result in exactly one 200 and one 409."""
    make_client = client_factory
    client_admin = await make_client()
    admin_token = await _create_admin_token(client_admin, postgres_url)

    # 1. Create a draft item
    create_res = await client_admin.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "topic_id": "daily_home",
            "ci_level": 0,
            "duration_seconds": 30,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "concurrency-test-item",
        },
    )
    assert create_res.status_code == 201
    item = create_res.json()
    item_id = item["id"]
    initial_revision = item["revision"]
    assert initial_revision == 1

    # 2. Setup barrier for simultaneous execution
    barrier = asyncio.Barrier(2)

    async def patch_worker(title: str, level: int):
        c = await make_client()
        await barrier.wait()
        return await c.patch(
            f"/staff/catalog/{item_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "revision": initial_revision,
                "title_internal": title,
                "ci_level": level,
            },
        )

    t1 = asyncio.create_task(patch_worker("winner-alpha", 1))
    t2 = asyncio.create_task(patch_worker("winner-beta", 2))
    res1, res2 = await asyncio.gather(t1, t2)

    statuses = {res1.status_code, res2.status_code}
    assert statuses == {200, 409}, f"Expected exactly one 200 and one 409, got: {res1.status_code}, {res2.status_code}"

    # Verify final item in DB
    get_res = await client_admin.get(
        f"/staff/catalog/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_res.status_code == 200
    final_item = get_res.json()
    assert final_item["revision"] == 2, f"Expected revision to be incremented to 2, got {final_item['revision']}"
    winner_res = res1 if res1.status_code == 200 else res2
    assert final_item["title_internal"] == winner_res.json()["title_internal"]


@pytest.mark.asyncio
async def test_race_between_patch_and_submit_qa(client_factory, postgres_url: str):
    """Racing PATCH and submit-qa must maintain state invariants without overwriting status."""
    make_client = client_factory
    client_admin = await make_client()
    admin_token = await _create_admin_token(client_admin, postgres_url)

    # 1. Create a draft item
    create_res = await client_admin.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "topic_id": "daily_home",
            "ci_level": 0,
            "duration_seconds": 30,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "race-qa-item",
        },
    )
    assert create_res.status_code == 201
    item_id = create_res.json()["id"]

    barrier = asyncio.Barrier(2)

    async def worker_patch():
        c = await make_client()
        await barrier.wait()
        return await c.patch(
            f"/staff/catalog/{item_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"revision": 1, "title_internal": "modified-during-qa-race"},
        )

    async def worker_submit_qa():
        c = await make_client()
        await barrier.wait()
        return await c.post(
            f"/staff/catalog/{item_id}/submit-qa",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    r_patch, r_qa = await asyncio.gather(worker_patch(), worker_submit_qa())

    # Get final state
    get_res = await client_admin.get(
        f"/staff/catalog/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    final_item = get_res.json()

    # Either submit-qa ran first -> patch fails with 400 (wrong status) or 409, and status is level_qa
    # Or patch ran first (200) -> submit-qa advances it to level_qa (revision 3)
    if r_patch.status_code == 200:
        assert r_qa.status_code == 200
        assert final_item["status"] == "level_qa"
        assert final_item["revision"] == 3
        assert final_item["title_internal"] == "modified-during-qa-race"
    else:
        assert r_patch.status_code in (400, 409)
        assert r_qa.status_code == 200
        assert final_item["status"] == "level_qa"
        assert final_item["revision"] == 2
