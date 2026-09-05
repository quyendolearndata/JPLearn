"""Docker Postgres for web E2E — Python replacement for apps/api/test/docker-db.cjs.

    python differential/db.py up|down|url

`up` starts the Compose `db-test` service in its own project, applies Alembic
migrations, seeds, and prints `E2E_DB_READY <url>`; `down` removes only that
project so the dev database `jplearn` is never touched.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "apps" / "api-python" / "tests"))
sys.path.insert(0, str(REPO / "apps" / "api-python" / "src"))

from pg_harness import start_docker_postgres, stop_docker_postgres  # noqa: E402

import argparse

PROJECT = "jplearn-web-e2e"


def _state_file(project: str) -> Path:
    return Path(tempfile.gettempdir()) / f"{project}-docker.json"


def up(project: str = PROJECT) -> int:
    stop_docker_postgres(project)
    url = start_docker_postgres(project, seed=True)
    _state_file(project).write_text(json.dumps({"project": project, "databaseUrl": url}), encoding="utf-8")
    print(f"E2E_DB_READY {url}")
    return 0


def down(project: str = PROJECT) -> int:
    stop_docker_postgres(project)
    _state_file(project).unlink(missing_ok=True)
    print("E2E_DB_STOPPED")
    return 0


def url(project: str = PROJECT) -> int:
    state = _state_file(project)
    if not state.exists():
        print(f"no running web E2E database for project '{project}'; run `db.py up` first", file=sys.stderr)
        return 1
    print(json.loads(state.read_text(encoding="utf-8"))["databaseUrl"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Docker Postgres for Web E2E")
    parser.add_argument("action", choices=["up", "down", "url"], nargs="?", default="up")
    parser.add_argument("--project", default=PROJECT, help="Docker compose project name")
    args = parser.parse_args()

    actions = {"up": up, "down": down, "url": url}
    return actions[args.action](args.project)


if __name__ == "__main__":
    sys.exit(main())
