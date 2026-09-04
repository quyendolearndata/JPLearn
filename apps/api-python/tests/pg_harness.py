"""Start / migrate jplearn_test. Alembic owns DDL (ADR-004) — never create_all."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[3]
API_PY = REPO / "apps" / "api-python"
COMPOSE = REPO / "docker-compose.yml"

if str(API_PY / "src") not in sys.path:
    sys.path.insert(0, str(API_PY / "src"))


def assert_test_database_url(database_url: str) -> None:
    path = urlparse(database_url).path
    if path != "/jplearn_test":
        raise RuntimeError(f"Refusing to run tests against non-test database: {path}")


def migrate_database(database_url: str, *, seed: bool = False) -> None:
    assert_test_database_url(database_url)
    from jplearn_api.migrate import upgrade

    upgrade(database_url)
    if seed:
        seed_database(database_url)


def seed_database(database_url: str) -> None:
    assert_test_database_url(database_url)
    import asyncio

    os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@jplearn.local")
    os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "password10")

    from jplearn_api.seed import seed_url

    asyncio.run(seed_url(database_url))


def _compose(project_name: str, args: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(REPO),
            "--file",
            str(COMPOSE),
            "--project-name",
            project_name,
            "--profile",
            "test",
            *args,
        ],
        cwd=REPO,
        check=kwargs.pop("check", True),
        text=True,
        capture_output=True,
        **kwargs,
    )


def start_docker_postgres(project_name: str, *, seed: bool = False, migrate: bool = True) -> str:
    subprocess.run(["docker", "version"], check=True, capture_output=True)
    try:
        _compose(project_name, ["up", "--detach", "db-test"])
        container_id = ""
        for _ in range(60):
            container_id = _compose(project_name, ["ps", "--quiet", "db-test"]).stdout.strip()
            if container_id:
                ready = subprocess.run(
                    ["docker", "exec", container_id, "pg_isready", "-U", "jplearn_test", "-d", "jplearn_test"],
                    capture_output=True,
                )
                if ready.returncode == 0:
                    break
            time.sleep(0.25)
        else:
            raise RuntimeError(f"Docker PostgreSQL did not become ready: {container_id}")
        port_output = _compose(project_name, ["port", "db-test", "5432"]).stdout.strip()
        port = port_output.rsplit(":", 1)[-1]
        if not port.isdigit():
            raise RuntimeError(f"Could not parse Docker PostgreSQL port: {port_output}")
        database_url = f"postgresql://jplearn_test:jplearn_test@127.0.0.1:{port}/jplearn_test"
        if migrate:
            migrate_database(database_url, seed=seed)
        return database_url
    except Exception:
        stop_docker_postgres(project_name)
        raise


def stop_docker_postgres(project_name: str) -> None:
    _compose(project_name, ["down", "--volumes", "--remove-orphans"], check=False)


def _can_connect(database_url: str) -> bool:
    parsed = urlparse(database_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def ensure_test_database() -> tuple[str, str | None]:
    """Return (database_url, docker_project_or_None)."""
    existing = os.environ.get("JPLEARN_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if existing and urlparse(existing).path == "/jplearn_test" and _can_connect(existing):
        migrate_database(existing)
        return existing, None
    project_name = f"jplearn-pytest-{os.getpid()}"
    return start_docker_postgres(project_name), project_name
