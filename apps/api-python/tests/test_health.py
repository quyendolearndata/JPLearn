def test_health_ok(client):
    response = client.get("/health", headers={"x-request-id": "py-health"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["x-request-id"] == "py-health"


def test_docs_off_by_default(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
