from __future__ import annotations

import asyncio
from uuid import uuid4

import asyncpg
from fastapi.testclient import TestClient

TOPICS = ("daily_home", "food", "body", "go_somewhere", "nature", "people")


def _database_url(client: TestClient) -> str:
    return client.app.state.settings.database_url


def _run(operation):
    return asyncio.run(operation)


def register(client: TestClient, email: str | None = None, password: str = "password10"):
    chosen = email or f"u{uuid4().hex[:12]}@example.com"
    response = client.post("/auth/register", json={"email": chosen, "password": password})
    assert response.status_code == 201, response.text
    return response


def grant_role(client: TestClient, user_id: str, role: str) -> None:
    async def _grant() -> None:
        conn = await asyncpg.connect(_database_url(client))
        try:
            await conn.execute(
                'INSERT INTO user_roles (user_id, role) VALUES ($1, $2::"Role") ON CONFLICT DO NOTHING',
                user_id,
                role,
            )
        finally:
            await conn.close()

    _run(_grant())


def ensure_topics(client: TestClient) -> None:
    async def _topics() -> None:
        conn = await asyncpg.connect(_database_url(client))
        try:
            for topic_id in TOPICS:
                await conn.execute(
                    "INSERT INTO topics (id, label_internal) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
                    topic_id,
                    topic_id,
                )
        finally:
            await conn.close()

    _run(_topics())


def insert_media(client: TestClient, catalog_item_id: str) -> str:
    asset_id = str(uuid4())
    storage_key = f"test/{catalog_item_id}.mp4"
    storage = getattr(client.app.state, "storage", None)
    if storage and hasattr(storage, "root"):
        path = storage.root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake media content")

    async def _insert() -> None:
        conn = await asyncpg.connect(_database_url(client))
        try:
            await conn.execute(
                """
                INSERT INTO media_assets (id, catalog_item_id, storage_key, mime)
                VALUES ($1, $2, $3, $4)
                """,
                asset_id,
                catalog_item_id,
                storage_key,
                "video/mp4",
            )
        finally:
            await conn.close()

    _run(_insert())
    return asset_id
