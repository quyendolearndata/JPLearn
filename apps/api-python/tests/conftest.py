import os
import tempfile

os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient

from jplearn_api.main import create_app
from jplearn_api.settings import Settings

from pg_harness import ensure_test_database, stop_docker_postgres


def _settings(database_url: str | None = None) -> Settings:
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-bytes-long-for-pyjwt-security")
    os.environ.setdefault("API_PUBLIC_URL", "http://localhost:3001")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://jplearn_test:jplearn_test@127.0.0.1:5432/jplearn_test",
    )
    return Settings(
        database_url=database_url or os.environ["DATABASE_URL"],
        jwt_secret=os.environ["JWT_SECRET"],
        api_public_url=os.environ.get("API_PUBLIC_URL"),
        storage_root=os.environ.get("STORAGE_ROOT"),
        openapi_ui=False,
    )


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(_settings())) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def live_database_url() -> str:
    url, project = ensure_test_database()
    try:
        yield url
    finally:
        if project:
            stop_docker_postgres(project)


@pytest.fixture
def live_client(live_database_url: str) -> TestClient:
    with tempfile.TemporaryDirectory() as storage:
        os.environ["STORAGE_ROOT"] = storage
        with TestClient(create_app(_settings(live_database_url))) as test_client:
            yield test_client
