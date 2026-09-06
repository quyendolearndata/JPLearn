"""T-CAT-005 / T-CMS-002 / NFR-SEC-002: real API and PostgreSQL workflow."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from helpers import ensure_topics, grant_role, insert_media, register
from test_catalog import _create_body


def staff(client, role="teacher"):
    account = register(client).json()
    grant_role(client, account["user"]["id"], role)
    return {"Authorization": f"Bearer {account['access_token']}"}, account["user"]["id"]


def item(client, headers):
    ensure_topics(client)
    response = client.post("/staff/catalog", headers=headers, json=_create_body())
    assert response.status_code == 201, response.text
    return response.json()["id"]


def post(client, headers, item_id, action, body=None, code=200):
    response = client.post(f"/staff/catalog/{item_id}/{action}", headers=headers, json=body)
    assert response.status_code == code, response.text
    return response


def test_staff_list_detail_and_edit_draft(live_client):
    h, _ = staff(live_client)
    item_id = item(live_client, h)
    path = f"/staff/catalog/{item_id}"
    response = live_client.patch(path, headers=h, json={"title_internal": "  new title  ", "ci_level": 2})
    assert response.status_code == 200
    assert response.json()["title_internal"] == "new title"
    assert response.json()["ci_level"] == 2
    detail = live_client.get(path, headers=h)
    assert detail.status_code == 200
    assert detail.json()["reviews"] == []
    assert detail.json()["qa_round"] == 0
    rows = live_client.get("/staff/catalog?status=draft&limit=100", headers=h).json()["items"]
    assert rows == sorted(rows, key=lambda row: row["id"])
    assert all(row["status"] == "draft" for row in rows)
    first = live_client.get("/staff/catalog?limit=1", headers=h).json()["items"]
    second = live_client.get("/staff/catalog?limit=1&offset=1", headers=h).json()["items"]
    assert len(first) == 1
    assert not second or first[0]["id"] != second[0]["id"]
    post(live_client, h, item_id, "submit-qa")
    assert live_client.patch(path, headers=h, json={"ci_level": 3}).status_code == 400
    assert live_client.get(f"/staff/catalog/{uuid4()}", headers=h).status_code == 404


@pytest.mark.parametrize("body", [{}, {"ci_level": None}, {"ci_level": 5}, {"duration_seconds": 0},
    {"title_internal": "  "}, {"status": "published"}, {"topic_id": "missing-topic"},
    {"qa_round": 10}, {"title_internal": "x" * 501}])
def test_patch_validation(live_client, body):
    h, _ = staff(live_client)
    item_id = item(live_client, h)
    assert live_client.patch(f"/staff/catalog/{item_id}", headers=h, json=body).status_code == 400
    assert live_client.get(f"/staff/catalog/{item_id}", headers=h).json()["title_internal"] == "pour water"


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "status=invalid"])
def test_list_validation(live_client, query):
    h, _ = staff(live_client)
    assert live_client.get(f"/staff/catalog?{query}", headers=h).status_code == 400


def test_learner_cannot_access_staff_workflow(live_client):
    h, _ = staff(live_client)
    item_id = item(live_client, h)
    learner = {"Authorization": "Bearer " + register(live_client).json()["access_token"]}
    for method, path, body in [
        ("get", "/staff/catalog", None), ("get", f"/staff/catalog/{item_id}", None),
        ("patch", f"/staff/catalog/{item_id}", {"title_internal": "changed"}),
        ("post", f"/staff/catalog/{item_id}/review", {"decision": "approve"}),
    ]:
        kwargs = {} if body is None else {"json": body}
        assert live_client.request(method, path, headers=learner, **kwargs).status_code == 403
        assert live_client.request(method, path, **kwargs).status_code == 401


def test_qa_reject_resubmit_approve_publish_and_invalidation(live_client):
    teacher, reviewer_id = staff(live_client)
    admin, _ = staff(live_client, "admin")
    item_id = item(live_client, teacher)
    insert_media(live_client, item_id)
    post(live_client, teacher, item_id, "review", {"decision": "approve"}, code=400)
    post(live_client, teacher, item_id, "submit-qa")
    post(live_client, admin, item_id, "publish", code=400)
    for body in [{"decision":"reject"}, {"decision":"reject","notes":"  "},
                 {"decision":"approve","reviewed_by":reviewer_id},
                 {"decision":"approve","notes":"x"*2001}]:
        post(live_client, teacher, item_id, "review", body, code=400)
    rejected = post(live_client, teacher, item_id, "review", {"decision":"reject","notes":"  Fix visual context  "})
    assert rejected.json()["status"] == "draft"
    post(live_client, teacher, item_id, "submit-qa")
    post(live_client, admin, item_id, "publish", code=400)
    post(live_client, teacher, item_id, "review", {"decision":"approve","notes":"Rubric checked"})
    post(live_client, teacher, item_id, "review", {"decision":"reject","notes":"late"}, code=400)
    post(live_client, teacher, item_id, "publish", code=403)
    post(live_client, admin, item_id, "publish")
    detail = live_client.get(f"/staff/catalog/{item_id}", headers=teacher).json()
    assert detail["qa_round"] == 2
    assert [row["decision"] for row in detail["reviews"]] == ["reject","approve"]
    assert detail["reviews"][0]["notes"] == "Fix visual context"
    assert all(row["reviewed_by"] == reviewer_id and row["reviewed_at"].endswith("Z") for row in detail["reviews"])
    learner = {"Authorization": "Bearer " + register(live_client).json()["access_token"]}
    public = next(row for row in live_client.get("/catalog", headers=learner).json()["items"] if row["id"]==item_id)
    assert not {"reviews","qa_round","notes","reviewed_by"}.intersection(public)
    post(live_client, admin, item_id, "unpublish")
    post(live_client, teacher, item_id, "submit-qa")
    post(live_client, admin, item_id, "publish", code=400)
    assert len(live_client.get(f"/staff/catalog/{item_id}", headers=teacher).json()["reviews"]) == 2


def test_media_is_immutable_after_submission(live_client):
    h, _ = staff(live_client)
    item_id = item(live_client, h)
    asset_id = insert_media(live_client, item_id)
    post(live_client, h, item_id, "submit-qa")
    response = live_client.post(f"/staff/catalog/{item_id}/media", headers=h,
        files={"file": ("clip.mp4", b"\x00\x00\x00\x18ftypmp42fake mp4 bytes", "video/mp4")})
    assert response.status_code == 400
    assert "draft" in response.json()["message"]
    response = live_client.post(f"/staff/media/{asset_id}/hls", headers=h)
    assert response.status_code == 400
    assert "draft" in response.json()["message"]


def test_concurrent_reviews_record_one_verdict(live_client):
    h, _ = staff(live_client)
    item_id = item(live_client, h)
    post(live_client, h, item_id, "submit-qa")
    def approve(_):
        return live_client.post(f"/staff/catalog/{item_id}/review", headers=h, json={"decision":"approve"}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(approve, range(2)))
    assert sorted(results) == [200,400]
    assert len(live_client.get(f"/staff/catalog/{item_id}", headers=h).json()["reviews"]) == 1
