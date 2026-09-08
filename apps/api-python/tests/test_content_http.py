"""Tests for Content HTTP responses (P1.1) and Capability Matrix Server-Side Gates (P1.9)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.read_models import UserDTO
from jplearn_api.entrypoints.http.app import create_app
from jplearn_api.entrypoints.http.roles import require_roles
from jplearn_api.entrypoints.http.security import require_user
from jplearn_api.settings import Settings


@pytest.fixture
def base_settings(tmp_path) -> Settings:
    return Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        api_public_url="http://localhost:8000",
        environment="test",
        storage_root=str(tmp_path),
        openapi_ui=False,
        # Capabilities enabled by default for positive testing
        video_scene_breakdown_enabled=True,
        personal_collections_enabled=True,
        content_reports_enabled=True,
        playback_tracking_enabled=True,
        staff_ai_enabled=True,
        scene_search_enabled=True,
    )


def test_content_response_model_validate_p1_1():
    """Verify ContentVersionPublic can model_validate a ContentVersionDTO without model_type error."""
    from jplearn_api.application.read_models import ContentVersionDTO, SceneDTO
    from jplearn_api.entrypoints.http.schemas import ContentVersionPublic

    dto = ContentVersionDTO(
        id="ver-123",
        catalog_item_id="00000000-0000-4000-8000-0000000000aa",
        version_number=1,
        revision=1,
        is_frozen=False,
        is_published=True,
        scenes=[
            SceneDTO(
                id="00000000-0000-4000-8000-000000000001",
                scene_index=0,
                start_time_seconds=0,
                end_time_seconds=15,
                title_jp="シーン1",
                transcript_jp="こんにちは",
            )
        ],
    )

    validated = ContentVersionPublic.model_validate(dto)
    assert validated.id == "ver-123"
    assert validated.catalog_item_id == "00000000-0000-4000-8000-0000000000aa"
    assert len(validated.scenes) == 1
    assert validated.scenes[0].title_jp == "シーン1"


def test_capability_matrix_gates_p1_9(base_settings: Settings):
    """Verify that when capability flags are disabled, server returns 403 Forbidden."""
    # Turn off capabilities
    disabled_settings = base_settings.model_copy(
        update={
            "video_scene_breakdown_enabled": False,
            "personal_collections_enabled": False,
            "content_reports_enabled": False,
            "playback_tracking_enabled": False,
        }
    )

    app = create_app(disabled_settings)

    # Auth overrides
    learner = UserDTO(id="u-learner", email="learner@test.com", roles=["learner"])
    teacher = UserDTO(id="u-teacher", email="teacher@test.com", roles=["teacher"])
    app.dependency_overrides[require_user] = lambda: learner
    app.dependency_overrides[require_roles("teacher", "admin")] = lambda: teacher

    with TestClient(app) as client:
        # 1. Content & Scenes routes return 403
        item_id = "00000000-0000-4000-8000-0000000000aa"
        res = client.get(f"/catalog/{item_id}/content")
        assert res.status_code == 403
        assert "video_scene_breakdown_enabled" in res.json()["message"]

        app.dependency_overrides[require_user] = lambda: teacher
        res = client.get(f"/staff/catalog/{item_id}/content")
        assert res.status_code == 403
        assert "video_scene_breakdown_enabled" in res.json()["message"]

        res = client.put(f"/staff/catalog/{item_id}/content", json={"version_revision": 1, "scenes": []})
        assert res.status_code == 403
        assert "video_scene_breakdown_enabled" in res.json()["message"]

        res = client.put(f"/me/saved-scenes/{item_id}")
        assert res.status_code == 403
        assert "video_scene_breakdown_enabled" in res.json()["message"]

        # 2. Personal Collections return 403
        res = client.post("/me/collections", json={"name": "My List"})
        assert res.status_code == 403
        assert "personal_collections_enabled" in res.json()["message"]

        res = client.get("/me/collections")
        assert res.status_code == 403
        assert "personal_collections_enabled" in res.json()["message"]

        # 3. Content Reports return 403
        res = client.post(
            f"/catalog/{item_id}/reports",
            json={
                "content_version_id": "ver-1",
                "category": "audio_quality",
                "description": "Sound is too low",
            },
        )
        assert res.status_code == 403
        assert "content_reports_enabled" in res.json()["message"]

        # 4. Playbacks start returns 403
        res = client.post(
            "/playbacks",
            json={
                "catalog_item_id": item_id,
                "device_id": "dev-1",
            },
        )
        assert res.status_code == 403
        assert "playback_tracking_enabled" in res.json()["message"]
