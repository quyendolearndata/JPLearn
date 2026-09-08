"""Start / migrate jplearn_test. Alembic owns DDL (ADR-004) — never create_all."""

import asyncio
import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

REPO = Path(__file__).resolve().parents[3]
API_PY = REPO / "apps" / "api-python"
COMPOSE = REPO / "docker-compose.yml"

_tracked_docker_projects: set[str] = set()


def _cleanup_tracked_projects() -> None:
    for project in list(_tracked_docker_projects):
        try:
            stop_docker_postgres(project)
        except Exception:
            pass


atexit.register(_cleanup_tracked_projects)

for sig in (signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(sig, lambda s, f: (_cleanup_tracked_projects(), sys.exit(128 + s)))
    except (ValueError, AttributeError):
        pass

if str(API_PY / "src") not in sys.path:
    sys.path.insert(0, str(API_PY / "src"))


def assert_test_database_url(database_url: str) -> None:
    path = urlparse(database_url).path
    if path != "/jplearn_test":
        raise RuntimeError(f"Refusing to run tests against non-test database: {path}")


def migrate_database(database_url: str, *, seed: bool = False) -> None:
    assert_test_database_url(database_url)
    from jplearn_api.entrypoints.cli.migrate import upgrade

    upgrade(database_url)
    if seed:
        seed_database(database_url)


def seed_database(database_url: str) -> None:
    assert_test_database_url(database_url)
    import asyncio

    os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@jplearn.local")
    os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "password10")

    from jplearn_api.entrypoints.cli.seed import seed_url

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


def _cleanup_stale_pytest_containers() -> None:
    """Find and clean up any orphaned jplearn-pytest-<pid> containers whose PID is dead."""
    try:
        res = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=jplearn-pytest-", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return
        current_pid = os.getpid()
        for name in res.stdout.strip().splitlines():
            parts = name.split("-")
            if len(parts) >= 3 and parts[0] == "jplearn" and parts[1] == "pytest":
                pid_str = parts[2]
                if pid_str.isdigit():
                    pid = int(pid_str)
                    if pid == current_pid:
                        continue
                    try:
                        os.kill(pid, 0)
                    except OSError:
                        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
    except Exception:
        pass


def start_docker_postgres(project_name: str, *, seed: bool = False, migrate: bool = True) -> str:
    subprocess.run(["docker", "version"], check=True, capture_output=True)
    _cleanup_stale_pytest_containers()
    _tracked_docker_projects.add(project_name)
    try:
        _compose(project_name, ["up", "--detach", "db-test"])
        container_id = ""
        for _ in range(60):
            container_id = _compose(project_name, ["ps", "--quiet", "db-test"]).stdout.strip()
            if container_id:
                ready = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_id,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "jplearn_test",
                        "-d",
                        "jplearn_test",
                    ],
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
        # The image's temporary initialization server accepts Unix sockets before
        # the final TCP server starts. Also verify Docker's published host port
        # before returning, including for fixtures that skip migrations.
        asyncio.run(_wait_for_database(database_url))
        if migrate:
            migrate_database(database_url, seed=seed)
        return database_url
    except Exception:
        stop_docker_postgres(project_name)
        raise


async def _wait_for_database(database_url: str) -> None:
    assert_test_database_url(database_url)
    deadline = time.monotonic() + 15
    while True:
        try:
            conn = await asyncpg.connect(database_url, timeout=1)
            try:
                await conn.fetchval("SELECT 1", timeout=1)
            finally:
                await conn.close(timeout=1)
            return
        except (OSError, TimeoutError, asyncpg.CannotConnectNowError):
            if time.monotonic() >= deadline:
                raise
            await asyncio.sleep(0.25)


def stop_docker_postgres(project_name: str) -> None:
    _tracked_docker_projects.discard(project_name)
    _compose(project_name, ["down", "--volumes", "--remove-orphans"], check=False)


def _can_connect(database_url: str) -> bool:
    async def probe() -> None:
        conn = await asyncpg.connect(database_url, timeout=1.5)
        try:
            await conn.fetchval("SELECT 1", timeout=1.5)
        finally:
            await conn.close(timeout=1.5)

    try:
        asyncio.run(probe())
        return True
    except Exception:
        return False


def ensure_test_database() -> tuple[str, str | None]:
    """Return (database_url, docker_project_or_None)."""
    existing = os.environ.get("JPLEARN_TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if existing and urlparse(existing).path == "/jplearn_test" and _can_connect(existing):
        migrate_database(existing)
        return existing, None
    project_name = f"jplearn-pytest-{os.getpid()}"
    return start_docker_postgres(project_name), project_name
