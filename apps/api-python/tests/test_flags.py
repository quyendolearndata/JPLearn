from helpers import grant_role, register


FLAG_DEFAULTS = {
    "speaking_enabled": False,
    "l1_subtitles_enabled": False,
    "grammar_enabled": False,
    "flashcards_enabled": False,
}


def test_get_flags_defaults_false(live_client):
    token = register(live_client).json()["access_token"]
    response = live_client.get("/flags", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == FLAG_DEFAULTS


def test_learner_cannot_patch_staff_flags(live_client):
    token = register(live_client).json()["access_token"]
    response = live_client.patch(
        "/staff/flags",
        headers={"Authorization": f"Bearer {token}"},
        json={**FLAG_DEFAULTS, "speaking_enabled": True},
    )
    assert response.status_code == 403
    assert response.json()["statusCode"] == 403
    assert "detail" not in response.json()


def test_admin_patch_flags_updates_all_keys(live_client):
    registered = register(live_client)
    grant_role(live_client, registered.json()["user"]["id"], "admin")
    token = registered.json()["access_token"]
    updated = {
        "speaking_enabled": True,
        "l1_subtitles_enabled": True,
        "grammar_enabled": False,
        "flashcards_enabled": True,
    }
    patch = live_client.patch(
        "/staff/flags",
        headers={"Authorization": f"Bearer {token}"},
        json=updated,
    )
    assert patch.status_code == 200
    assert patch.json() == updated
    listed = live_client.get("/flags", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    assert listed.json() == updated
    reset = live_client.patch(
        "/staff/flags",
        headers={"Authorization": f"Bearer {token}"},
        json=FLAG_DEFAULTS,
    )
    assert reset.status_code == 200
