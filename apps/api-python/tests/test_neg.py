from helpers import register

TEXTBOOK_PATHS = (
    "/flashcards",
    "/grammar",
    "/grammar/lessons",
    "/vocabulary",
    "/translations",
)


def test_textbook_routes_are_404(live_client):
    token = register(live_client).json()["access_token"]
    for path in TEXTBOOK_PATHS:
        response = live_client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 404, path
        assert "detail" not in response.json()
