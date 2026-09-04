from pathlib import Path
from urllib.parse import urlparse

from helpers import ensure_topics, grant_role, register

MANIFEST = "\n".join(
    [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:4",
        "#EXTINF:4.000,",
        "segment-000.ts",
        "#EXT-X-ENDLIST",
        "",
    ],
)


def _admin(live_client):
    ensure_topics(live_client)
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "admin")
    grant_role(live_client, registered.json()["user"]["id"], "teacher")
    return registered.json()["access_token"]


def _upload(live_client, token: str) -> tuple[str, str]:
    created = live_client.post(
        "/staff/catalog",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "topic_id": "daily_home",
            "ci_level": 0,
            "duration_seconds": 4,
            "media_type": "video",
            "visual_support": "high",
            "title_internal": "hls",
        },
    )
    item_id = created.json()["id"]
    uploaded = live_client.post(
        f"/staff/catalog/{item_id}/media",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("clip.mp4", b"fake mp4 bytes", "video/mp4")},
    )
    assert uploaded.status_code == 201
    return item_id, uploaded.json()["id"]


def _write_hls_bundle(live_client, asset_id: str) -> None:
    root = Path(live_client.app.state.settings.storage_root)
    directory = root / "hls" / asset_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.m3u8").write_text(MANIFEST, encoding="utf-8")
    (directory / "segment-000.ts").write_bytes(b"fake ts segment")


def test_register_requires_manifest_on_disk(live_client):
    admin = _admin(live_client)
    _, asset_id = _upload(live_client, admin)
    response = live_client.post(
        f"/staff/media/{asset_id}/hls",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert response.status_code == 400


def test_learner_cannot_register_hls(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    _, asset_id = _upload(live_client, admin)
    response = live_client.post(
        f"/staff/media/{asset_id}/hls",
        headers={"Authorization": f"Bearer {learner}"},
    )
    assert response.status_code == 403


def test_register_serves_manifest_and_segments(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    item_id, asset_id = _upload(live_client, admin)
    _write_hls_bundle(live_client, asset_id)

    registered = live_client.post(
        f"/staff/media/{asset_id}/hls",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert registered.status_code == 201, registered.text
    parsed = urlparse(registered.json()["hls_url"])
    assert parsed.path == f"/media/{asset_id}/hls/index.m3u8"
    assert "sig=" in parsed.query

    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200
    assert live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200

    listed = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    item = next(row for row in listed.json()["items"] if row["id"] == item_id)
    assert urlparse(item["hls_url"]).path == f"/media/{asset_id}/hls/index.m3u8"

    manifest = live_client.get(
        f"/media/{asset_id}/hls/index.m3u8",
        headers={"Authorization": f"Bearer {learner}"},
    )
    assert manifest.status_code == 200
    assert "application/vnd.apple.mpegurl" in manifest.headers["content-type"]
    assert manifest.headers["x-content-type-options"] == "nosniff"
    assert "#EXTM3U" in manifest.text

    segment = live_client.get(
        f"/media/{asset_id}/hls/segment-000.ts",
        headers={"Authorization": f"Bearer {learner}"},
    )
    assert segment.status_code == 200
    assert "video/mp2t" in segment.headers["content-type"]
    assert segment.headers["x-content-type-options"] == "nosniff"
    assert segment.content == b"fake ts segment"


def test_signed_manifest_rewrites_segment_uris(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    item_id, asset_id = _upload(live_client, admin)
    _write_hls_bundle(live_client, asset_id)
    assert live_client.post(
        f"/staff/media/{asset_id}/hls",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 201
    assert live_client.post(
        f"/staff/catalog/{item_id}/submit-qa",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200
    assert live_client.post(
        f"/staff/catalog/{item_id}/publish",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 200

    listed = live_client.get("/catalog", headers={"Authorization": f"Bearer {learner}"})
    item = next(row for row in listed.json()["items"] if row["id"] == item_id)
    signed = urlparse(item["hls_url"])

    manifest = live_client.get(f"{signed.path}?{signed.query}")
    assert manifest.status_code == 200
    segment_line = next(
        line for line in manifest.text.split("\n") if line.strip() and not line.strip().startswith("#")
    )
    assert segment_line.startswith("segment-000.ts?exp=")
    assert "&sig=" in segment_line

    segment = live_client.get(f"/media/{asset_id}/hls/{segment_line}")
    assert segment.status_code == 200


def test_rejects_traversal_and_unsupported_types(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    _, asset_id = _upload(live_client, admin)
    _write_hls_bundle(live_client, asset_id)
    assert live_client.post(
        f"/staff/media/{asset_id}/hls",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 201

    assert live_client.get(
        f"/media/{asset_id}/hls/evil.exe",
        headers={"Authorization": f"Bearer {learner}"},
    ).status_code == 400
    assert live_client.get(
        f"/media/{asset_id}/hls/..%2Fsecret.m3u8",
        headers={"Authorization": f"Bearer {learner}"},
    ).status_code == 400


def test_requires_auth_and_404_missing(live_client):
    admin = _admin(live_client)
    learner = register(live_client).json()["access_token"]
    _, asset_id = _upload(live_client, admin)
    _write_hls_bundle(live_client, asset_id)
    assert live_client.post(
        f"/staff/media/{asset_id}/hls",
        headers={"Authorization": f"Bearer {admin}"},
    ).status_code == 201

    assert live_client.get(f"/media/{asset_id}/hls/index.m3u8").status_code == 401
    assert live_client.get(
        f"/media/{asset_id}/hls/segment-999.ts",
        headers={"Authorization": f"Bearer {learner}"},
    ).status_code == 404
