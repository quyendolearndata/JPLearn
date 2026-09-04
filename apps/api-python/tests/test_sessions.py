import asyncio
import json
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from helpers import register


def _db_url(client):
    return client.app.state.settings.database_url


def _shift_started_at(client, session_id: str, seconds_ago: float) -> None:
    async def _update() -> None:
        conn = await asyncpg.connect(_db_url(client))
        try:
            await conn.execute(
                "UPDATE learning_sessions SET started_at = $1 WHERE id = $2",
                (datetime.now(UTC) - timedelta(seconds=seconds_ago)).replace(tzinfo=None),
                session_id,
            )
        finally:
            await conn.close()

    asyncio.run(_update())


def _events_for(client, session_id: str) -> list[tuple[str, dict]]:
    async def _read() -> list[tuple[str, dict]]:
        conn = await asyncpg.connect(_db_url(client))
        try:
            rows = await conn.fetch(
                "SELECT type, payload FROM learning_events WHERE session_id = $1 ORDER BY created_at ASC, id ASC",
                session_id,
            )
            return [
                (row["type"], json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"])
                for row in rows
            ]
        finally:
            await conn.close()

    return asyncio.run(_read())


def test_progress_requires_auth(live_client):
    assert live_client.get("/progress").status_code == 401


def test_start_end_records_events_and_progress(live_client):
    registered = register(live_client)
    token = registered.json()["access_token"]
    user_id = registered.json()["user"]["id"]

    started = live_client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_class": "web"},
    )
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["device_class"] == "web"
    assert body["ended_at"] is None
    assert body["duration_seconds"] is None
    assert "started_at" in body and body["started_at"].endswith("Z")

    second = live_client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_class": "web"},
    )
    assert second.status_code == 201

    async def _device_count() -> int:
        conn = await asyncpg.connect(_db_url(live_client))
        try:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM devices WHERE user_id = $1 AND device_class = 'web'",
                user_id,
            )
        finally:
            await conn.close()

    assert asyncio.run(_device_count()) == 1

    events = _events_for(live_client, body["id"])
    assert [event[0] for event in events] == ["session_started", "level_exposed"]
    assert events[1][1] == {"ci_level": 0}

    _shift_started_at(live_client, body["id"], 120)
    ended = live_client.post(
        f"/sessions/{body['id']}/end",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert ended.status_code == 200
    assert ended.json() == {"minutes_comprehensible": 2, "current_ci_level": 0}

    progress = live_client.get("/progress", headers={"Authorization": f"Bearer {token}"})
    assert progress.status_code == 200
    assert progress.json() == {"minutes_comprehensible": 2, "current_ci_level": 0}

    event_types = sorted(event[0] for event in _events_for(live_client, body["id"]))
    assert event_types == [
        "level_exposed",
        "minutes_comprehensible",
        "session_ended",
        "session_started",
    ]
    minutes_payload = next(
        event[1] for event in _events_for(live_client, body["id"]) if event[0] == "minutes_comprehensible"
    )
    assert minutes_payload == {"minutes": 2}


def test_end_forbidden_other_user_and_double_end(live_client):
    first = register(live_client).json()["access_token"]
    second = register(live_client).json()["access_token"]
    started = live_client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {first}"},
        json={"device_class": "phone"},
    )
    assert started.status_code == 201
    session_id = started.json()["id"]
    assert live_client.post(
        f"/sessions/{session_id}/end",
        headers={"Authorization": f"Bearer {second}"},
    ).status_code == 403
    assert live_client.post(
        f"/sessions/{session_id}/end",
        headers={"Authorization": f"Bearer {first}"},
    ).status_code == 200
    assert live_client.post(
        f"/sessions/{session_id}/end",
        headers={"Authorization": f"Bearer {first}"},
    ).status_code == 400


def test_zombie_session_counts_zero_minutes(live_client):
    token = register(live_client).json()["access_token"]
    started = live_client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_class": "ipad"},
    )
    session_id = started.json()["id"]
    _shift_started_at(live_client, session_id, 4 * 60 * 60 + 10)
    ended = live_client.post(
        f"/sessions/{session_id}/end",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ended.status_code == 200
    assert ended.json()["minutes_comprehensible"] == 0


def test_invalid_device_class_is_400(live_client):
    token = register(live_client).json()["access_token"]
    response = live_client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_class": "tv"},
    )
    assert response.status_code == 400
    assert "detail" not in response.json()


def test_progress_keys_exactly_two(live_client):
    token = register(live_client).json()["access_token"]
    progress = live_client.get("/progress", headers={"Authorization": f"Bearer {token}"})
    assert sorted(progress.json().keys()) == ["current_ci_level", "minutes_comprehensible"]


def test_pure_minutes_from_duration():
    from jplearn_api.session_policy import minutes_from_duration

    assert minutes_from_duration(-10) == 0
    assert minutes_from_duration(-1) == 0
    assert minutes_from_duration(0) == 0
    assert minutes_from_duration(59) == 0
    assert minutes_from_duration(60) == 1
    assert minutes_from_duration(119) == 1
    assert minutes_from_duration(120) == 2
    assert minutes_from_duration(4 * 3600) == 240
    assert minutes_from_duration(4 * 3600 + 1) == 0
    assert minutes_from_duration(5 * 3600) == 0


@pytest.mark.asyncio
async def test_concurrent_end_same_session_exactly_once(live_database_url: str):
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from jplearn_api.db import async_database_url
    from jplearn_api.session_policy import SessionAlreadyEnded
    from jplearn_api.sessions_service import end

    conn = await asyncpg.connect(live_database_url)
    user_id = str(uuid4())
    session_id = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)
    started_at = now - timedelta(seconds=120)
    try:
        await conn.execute("INSERT INTO users (id, email, password_hash, token_version) VALUES ($1, $2, 'hash', 0)", user_id, f"{user_id}@test.com")
        await conn.execute("INSERT INTO learner_progress (user_id, minutes_comprehensible, current_ci_level, updated_at) VALUES ($1, 0, 0, $2)", user_id, now)
        await conn.execute("INSERT INTO learning_sessions (id, user_id, device_class, started_at) VALUES ($1, $2, 'phone', $3)", session_id, user_id, started_at)
    finally:
        await conn.close()

    engine = create_async_engine(async_database_url(live_database_url), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def call_end():
        async with factory() as session:
            try:
                res = await end(session, user_id, session_id)
                return ("ok", res)
            except SessionAlreadyEnded:
                return ("already_ended", None)
            except Exception as e:
                return ("error", type(e).__name__)

    results = await asyncio.gather(call_end(), call_end())
    await engine.dispose()

    statuses = [r[0] for r in results]
    assert sorted(statuses) == ["already_ended", "ok"], f"Expected 1 ok and 1 already_ended, got {statuses}"

    conn = await asyncpg.connect(live_database_url)
    try:
        mins = await conn.fetchval("SELECT minutes_comprehensible FROM learner_progress WHERE user_id = $1", user_id)
        assert mins == 2, f"Expected 2 minutes, got {mins}"

        end_events = await conn.fetchval("SELECT count(*) FROM learning_events WHERE session_id = $1 AND type = 'session_ended'", session_id)
        min_events = await conn.fetchval("SELECT count(*) FROM learning_events WHERE session_id = $1 AND type = 'minutes_comprehensible'", session_id)
        assert end_events == 1
        assert min_events == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_concurrent_end_different_sessions_no_lost_update(live_database_url: str):
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from jplearn_api.db import async_database_url
    from jplearn_api.sessions_service import end

    conn = await asyncpg.connect(live_database_url)
    user_id = str(uuid4())
    s1 = str(uuid4())
    s2 = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)
    started_s1 = now - timedelta(seconds=180)  # 3 minutes
    started_s2 = now - timedelta(seconds=300)  # 5 minutes
    try:
        await conn.execute("INSERT INTO users (id, email, password_hash, token_version) VALUES ($1, $2, 'hash', 0)", user_id, f"{user_id}@test.com")
        await conn.execute("INSERT INTO learner_progress (user_id, minutes_comprehensible, current_ci_level, updated_at) VALUES ($1, 10, 0, $2)", user_id, now)
        await conn.execute("INSERT INTO learning_sessions (id, user_id, device_class, started_at) VALUES ($1, $2, 'web', $3)", s1, user_id, started_s1)
        await conn.execute("INSERT INTO learning_sessions (id, user_id, device_class, started_at) VALUES ($1, $2, 'phone', $3)", s2, user_id, started_s2)
    finally:
        await conn.close()

    engine = create_async_engine(async_database_url(live_database_url), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def end_s(sid):
        async with factory() as session:
            return await end(session, user_id, sid)

    await asyncio.gather(end_s(s1), end_s(s2))
    await engine.dispose()

    conn = await asyncpg.connect(live_database_url)
    try:
        final_mins = await conn.fetchval("SELECT minutes_comprehensible FROM learner_progress WHERE user_id = $1", user_id)
        assert final_mins == 18, f"Expected 18 minutes (10 + 3 + 5), got {final_mins}"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_end_session_failure_rolls_back_atomically(live_database_url: str):
    from unittest.mock import patch
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from jplearn_api.db import async_database_url
    from jplearn_api.sessions_service import end

    conn = await asyncpg.connect(live_database_url)
    user_id = str(uuid4())
    session_id = str(uuid4())
    now = datetime.now(UTC).replace(tzinfo=None)
    started_at = now - timedelta(seconds=120)
    try:
        await conn.execute("INSERT INTO users (id, email, password_hash, token_version) VALUES ($1, $2, 'hash', 0)", user_id, f"{user_id}@test.com")
        await conn.execute("INSERT INTO learner_progress (user_id, minutes_comprehensible, current_ci_level, updated_at) VALUES ($1, 5, 0, $2)", user_id, now)
        await conn.execute("INSERT INTO learning_sessions (id, user_id, device_class, started_at) VALUES ($1, $2, 'web', $3)", session_id, user_id, started_at)
    finally:
        await conn.close()

    engine = create_async_engine(async_database_url(live_database_url), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    with patch("jplearn_api.sessions_service.minutes_from_duration", side_effect=RuntimeError("simulated event failure")):
        async with factory() as session:
            with pytest.raises(RuntimeError, match="simulated event failure"):
                await end(session, user_id, session_id)

    await engine.dispose()

    conn = await asyncpg.connect(live_database_url)
    try:
        ended_at = await conn.fetchval("SELECT ended_at FROM learning_sessions WHERE id = $1", session_id)
        mins = await conn.fetchval("SELECT minutes_comprehensible FROM learner_progress WHERE user_id = $1", user_id)
        assert ended_at is None
        assert mins == 5
    finally:
        await conn.close()

