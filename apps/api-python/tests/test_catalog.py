from helpers import ensure_topics, grant_role, insert_media, register


def _admin(live_client):
    ensure_topics(live_client)
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "admin")
    grant_role(live_client, registered.json()["user"]["id"], "teacher")
    return registered.json()["access_token"]


def _create_body(**overrides):
    body = {
        "topic_id": "daily_home",
        "ci_level": 0,
        "duration_seconds": 30,
        "media_type": "video",
        "visual_support": "high",
        "title_internal": "pour water",
    }
    body.update(overrides)
    return body


def test_learner_cannot_create_catalog(live_client):
    ensure_topics(live_client)
    token = register(live_client).json()["access_token"]
    response = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {token}"},
        json=_create_body(topic_id="food"),
    )
    assert response.status_code == 403


def test_draft_hidden_until_qa_and_publish_without_l1_fields(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    created = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {admin}"},
        json=_create_body(),
    )
    assert created.status_code == 201, created.text
    assert created.json()["has_l1_translation"] is False
    assert created.json()["status"] == "draft"
    item_id = created.json()["id"]

    listed = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    assert listed.status_code == 200
    assert all(item["id"] != item_id for item in listed.json()["items"])

    insert_media(live_client, item_id)
    qa = live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert qa.status_code == 200
    published = live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert published.status_code == 200

    shown = live_client.get(
        "/catalog?ci_level=0",
        headers={"Authorization": f"Bearer {learner}"},
    )
    assert shown.status_code == 200
    item = next(row for row in shown.json()["items"] if row["id"] == item_id)
    assert "title_internal" not in item
    assert "has_l1_translation" not in item
    assert "translation_vi" not in item


def test_publish_from_draft_is_400(live_client):
    admin = _admin(live_client)
    created = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {admin}"},
        json=_create_body(topic_id="food", ci_level=1, title_internal="skip"),
    )
    assert created.status_code == 201
    blocked = live_client.post(
        f"/staff/catalog/{created.json()['id']}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert blocked.status_code == 400


def test_publish_without_media_then_after_media(live_client):
    admin = _admin(live_client)
    created = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {admin}"},
        json=_create_body(topic_id="body", duration_seconds=12, title_internal="no-media"),
    )
    item_id = created.json()["id"]
    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200
    blocked = live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert blocked.status_code == 400
    assert "without media" in str(blocked.json()["message"])
    insert_media(live_client, item_id)
    published = live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"


def test_unpublish_hides_from_learners(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    created = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {admin}"},
        json=_create_body(topic_id="nature", duration_seconds=15, visual_support="medium", title_internal="unpublish-me"),
    )
    item_id = created.json()["id"]
    assert live_client.post(
        f"/staff/catalog/{item_id}/unpublish",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 400
    assert live_client.post(
        f"/staff/catalog/{item_id}/unpublish",
        headers={"Authorization": f"Bearer {learner}"},
    ).status_code == 403

    insert_media(live_client, item_id)
    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200
    assert live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200
    visible = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    assert any(item["id"] == item_id for item in visible.json()["items"])

    unpublished = live_client.post(
        f"/staff/catalog/{item_id}/unpublish",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["status"] == "draft"
    hidden = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    assert all(item["id"] != item_id for item in hidden.json()["items"])


def test_teacher_cannot_publish(live_client):
    ensure_topics(live_client)
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "teacher")
    token = registered.json()["access_token"]
    created = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {token}"},
        json=_create_body(title_internal="teacher-draft"),
    )
    assert created.status_code == 201
    publish = live_client.post(
        f"/staff/catalog/{created.json()['id']}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert publish.status_code == 403
