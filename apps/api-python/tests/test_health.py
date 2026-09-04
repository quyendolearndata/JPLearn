def test_health_ok(client):
    response = client.get("/health", headers={"x-request-id": "py-health"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["x-request-id"] == "py-health"


def test_docs_off_by_default(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_ready_ok(live_client):
    response = live_client.get("/ready", headers={"x-request-id": "py-ready"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "database": "up", "storage": "up"}
    assert response.headers["x-request-id"] == "py-ready"


def test_ready_db_down(live_client):
    from unittest.mock import AsyncMock
    from jplearn_api.deps import get_session

    app = live_client.app
    mock_session = AsyncMock()
    mock_session.execute.side_effect = RuntimeError("DB connection lost")

    async def _mock_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = _mock_get_session
    try:
        response = live_client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"ok": False, "database": "down", "storage": "up"}
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_ready_storage_down(live_client):
    from unittest.mock import AsyncMock
    from jplearn_api.deps import get_storage
    from jplearn_api.storage import StoragePort

    app = live_client.app
    mock_storage = AsyncMock(spec=StoragePort)
    mock_storage.exists.side_effect = RuntimeError("Storage disk failure")

    app.dependency_overrides[get_storage] = lambda: mock_storage
    try:
        response = live_client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"ok": False, "database": "up", "storage": "down"}
    finally:
        app.dependency_overrides.pop(get_storage, None)

