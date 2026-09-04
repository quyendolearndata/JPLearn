import asyncio
import json
from datetime import UTC, datetime, timedelta

import asyncpg
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
