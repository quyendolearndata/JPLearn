from urllib.parse import urlparse

from helpers import ensure_topics, grant_role, register


def _admin(live_client):
    ensure_topics(live_client)
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "admin")
    grant_role(live_client, registered.json()["user"]["id"], "teacher")
    return registered.json()["access_token"]


def _create_item(live_client, token: str, **overrides):
    body = {
        "topic_id": "daily_home",
        "ci_level": 0,
        "duration_seconds": 4,
        "media_type": "video",
        "visual_support": "high",
        "title_internal": "media",
    }
    body.update(overrides)
    response = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _publish(live_client, token: str, item_id: str):
    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200
    assert live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    ).status_code == 200


def test_upload_and_playback_dual_mode(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    item_id = _create_item(live_client, admin)

    uploaded = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("tiny.mp4", b"tiny media", "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["playback_url"].startswith("http://")
    asset_id = uploaded.json()["id"]

    _publish(live_client, admin, item_id)
    listed = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    item = next(row for row in listed.json()["items"] if row["id"] == item_id)
    parsed = urlparse(item["playback_url"])
    assert parsed.query and "sig=" in parsed.query

    playback = live_client.get(
        f"/media/{asset_id}",
        headers={"Authorization": f"Bearer {learner}"},
    )
    assert playback.status_code == 200
    assert playback.headers["x-content-type-options"] == "nosniff"
    assert playback.content == b"tiny media"

    signed = live_client.get(f"{parsed.path}?{parsed.query}")
    assert signed.status_code == 200
    assert signed.content == b"tiny media"

    bad = live_client.get(f"/media/{asset_id}?exp=1&sig={'ab' * 32}")
    assert bad.status_code == 401


def test_learner_cannot_upload_and_empty_file_400(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    item_id = _create_item(live_client, admin, media_type="audio", visual_support="low", title_internal="empty")

    forbidden = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {learner}"},
        files={"file": ("learner.mp3", b"learner", "audio/mpeg")},
    )
    assert forbidden.status_code == 403

    empty = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("empty.mp3", b"", "audio/mpeg")},
    )
    assert empty.status_code == 400


def test_media_requires_auth(live_client):
    admin = _admin(live_client)
    item_id = _create_item(live_client, admin)
    uploaded = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("clip.mp4", b"bytes", "video/mp4")},
    )
    asset_id = uploaded.json()["id"]
    assert live_client.get(f"/media/{asset_id}").status_code == 401
