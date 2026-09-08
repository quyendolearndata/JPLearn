from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jplearn_api.application.read_models import UserDTO
from jplearn_api.entrypoints.http.app import create_app
from jplearn_api.entrypoints.http.security import require_user
from jplearn_api.settings import Settings

CAPABILITY_DEFAULTS = {
    "video_scene_breakdown_enabled": False,
    "smart_stream_enabled": False,
    "interactive_dual_subs_enabled": False,
    "immersion_lookup_enabled": False,
    "personal_collections_enabled": False,
    "content_reports_enabled": False,
    "playback_tracking_enabled": False,
    "scene_search_enabled": False,
    "staff_ai_enabled": False,
}


def _dummy_user() -> UserDTO:
    return UserDTO(
        id="00000000-0000-4000-8000-0000000000aa",
        email="learner@example.com",
        roles=["learner"],
    )


def test_get_capabilities_unauthorized_without_token(client: TestClient):
    response = client.get("/capabilities")
    assert response.status_code == 401
    body = response.json()
    assert body["statusCode"] == 401


def test_get_capabilities_defaults_all_false(client: TestClient):
    client.app.dependency_overrides[require_user] = _dummy_user
    try:
        response = client.get("/capabilities")
        assert response.status_code == 200
        assert response.json() == CAPABILITY_DEFAULTS
    finally:
        client.app.dependency_overrides.pop(require_user, None)


def test_get_capabilities_reflects_configured_settings():
    custom_settings = Settings(
        database_url="postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
        jwt_secret="test-secret-at-least-32-bytes-long-for-pyjwt-security",
        openapi_ui=False,
        video_scene_breakdown_enabled=True,
        smart_stream_enabled=True,
        interactive_dual_subs_enabled=False,
        immersion_lookup_enabled=True,
        personal_collections_enabled=True,
        content_reports_enabled=True,
        playback_tracking_enabled=True,
        scene_search_enabled=True,
        staff_ai_enabled=True,
    )
    app = create_app(custom_settings)
    app.dependency_overrides[require_user] = _dummy_user
    with TestClient(app) as test_client:
        response = test_client.get("/capabilities")
        assert response.status_code == 200
        expected = {
            **CAPABILITY_DEFAULTS,
            "video_scene_breakdown_enabled": True,
            "smart_stream_enabled": True,
            "immersion_lookup_enabled": True,
            "personal_collections_enabled": True,
            "content_reports_enabled": True,
            "playback_tracking_enabled": True,
            "scene_search_enabled": True,
            "staff_ai_enabled": True,
        }
        assert response.json() == expected
