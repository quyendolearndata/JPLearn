"""UC-L06 sync — T-ID-002, T-PRG-004, T-NFR-X1.

Port of apps/api/test/sync.e2e-spec.ts. One identity on three independent
session tokens (web / phone / ipad) must resolve to the same user, see the same
published catalog, and read the same server-side progress. Progress belongs to
the user, not the device: exactly one learner_progress row regardless of how
many device classes appear.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import asyncpg

from helpers import register


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db(client):
    return client.app.state.settings.database_url


def _run(client, coro_factory):
    async def _go():
        conn = await asyncpg.connect(_db(client))
        try:
            return await coro_factory(conn)
        finally:
            await conn.close()

    return asyncio.run(_go())


def _seed_topic_and_items(client, user_id: str) -> tuple[str, str]:
    topic_id = f"sync-topic-{uuid4().hex[:8]}"
    published_id, draft_id = str(uuid4()), str(uuid4())

    async def _insert(conn):
        await conn.execute(
            "INSERT INTO topics (id, label_internal) VALUES ($1, $1)",
            topic_id,
        )
        await conn.executemany(
            """
            INSERT INTO catalog_items (
                id, topic_id, ci_level, duration_seconds, media_type, visual_support,
                status, title_internal, created_by
            ) VALUES ($1, $2, 0, $3, $4::"MediaType", $5::"VisualSupport",
                      $6::"CatalogStatus", $7, $8)
            """,
            [
                (published_id, topic_id, 45, "video", "high", "published", f"sync-published-{topic_id}", user_id),
                (draft_id, topic_id, 30, "audio", "medium", "draft", f"sync-draft-{topic_id}", user_id),
            ],
        )

    _run(client, _insert)
    return published_id, draft_id


def _shift_started_at(client, session_id: str, seconds: int) -> None:
    _run(
        client,
        lambda conn: conn.execute(
            "UPDATE learning_sessions SET started_at = NOW() - make_interval(secs => $1) WHERE id = $2",
            seconds,
            session_id,
        ),
    )


def _progress(client, token: str) -> dict:
    response = client.get("/progress", headers=_bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_same_identity_same_catalog_same_progress_across_devices(live_client):
    email = f"sync-{uuid4().hex[:10]}@example.com"
    password = "password10"

    web = register(live_client, email, password).json()
    user_id = web["user"]["id"]

    def login() -> str:
        response = live_client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    tokens = {"web": web["access_token"], "phone": login(), "ipad": login()}

    published_id, draft_id = _seed_topic_and_items(live_client, user_id)

    # FR-ID-002: three independent tokens, one identity.
    for token in tokens.values():
        me = live_client.get("/me", headers=_bearer(token))
        assert me.status_code == 200
        assert me.json()["id"] == user_id
        assert me.json()["email"] == email

    # UC-L06 main: identical published catalog on all three clients.
    def _strip_sig(cat: dict) -> dict:
        import copy
        res = copy.deepcopy(cat)
        for it in res.get("items", []):
            if it.get("playback_url"):
                it["playback_url"] = it["playback_url"].split("?")[0]
            if it.get("hls_url"):
                it["hls_url"] = it["hls_url"].split("?")[0]
        return res

    catalogs = [live_client.get("/catalog", headers=_bearer(token)).json() for token in tokens.values()]
    assert _strip_sig(catalogs[1]) == _strip_sig(catalogs[0])
    assert _strip_sig(catalogs[2]) == _strip_sig(catalogs[0])
    ids = [item["id"] for item in catalogs[0]["items"]]
    assert published_id in ids
    assert draft_id not in ids

    zero = {"minutes_comprehensible": 0, "current_ci_level": 0}
    for token in tokens.values():
        assert _progress(live_client, token) == zero

    # phone studies 3 minutes
    phone_session = live_client.post(
        "/sessions",
        headers=_bearer(tokens["phone"]),
        json={"device_class": "phone"},
    )
    assert phone_session.status_code == 201, phone_session.text
    assert phone_session.json()["device_class"] == "phone"
    _shift_started_at(live_client, phone_session.json()["id"], 180)
    phone_end = live_client.post(
        f"/sessions/{phone_session.json()['id']}/end",
        headers=_bearer(tokens["phone"]),
    )
    assert phone_end.status_code == 200, phone_end.text
    assert phone_end.json()["minutes_comprehensible"] == 3

    # FR-PRG-004: web and ipad read the same server-side value.
    three = {"minutes_comprehensible": 3, "current_ci_level": 0}
    assert _progress(live_client, tokens["web"]) == three
    assert _progress(live_client, tokens["ipad"]) == three

    # Reverse direction: ipad adds a minute, the others see the new total.
    ipad_session = live_client.post(
        "/sessions",
        headers=_bearer(tokens["ipad"]),
        json={"device_class": "ipad"},
    )
    assert ipad_session.status_code == 201
    assert ipad_session.json()["device_class"] == "ipad"
    _shift_started_at(live_client, ipad_session.json()["id"], 60)
    assert live_client.post(
        f"/sessions/{ipad_session.json()['id']}/end",
        headers=_bearer(tokens["ipad"]),
    ).status_code == 200

    four = {"minutes_comprehensible": 4, "current_ci_level": 0}
    assert _progress(live_client, tokens["web"]) == four
    assert _progress(live_client, tokens["phone"]) == four

    # web opens a session too → all three device classes recorded once each.
    assert live_client.post(
        "/sessions",
        headers=_bearer(tokens["web"]),
        json={"device_class": "web"},
    ).status_code == 201

    device_classes = _run(
        live_client,
        lambda conn: conn.fetch(
            "SELECT device_class::text AS device_class FROM devices WHERE user_id = $1",
            user_id,
        ),
    )
    assert sorted(row["device_class"] for row in device_classes) == ["ipad", "phone", "web"]

    progress_rows = _run(
        live_client,
        lambda conn: conn.fetchval("SELECT count(*) FROM learner_progress WHERE user_id = $1", user_id),
    )
    assert progress_rows == 1, "progress must be per user, not per device"
