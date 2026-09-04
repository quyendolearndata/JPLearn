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

PROJECT = "jplearn-web-e2e"
STATE = Path(tempfile.gettempdir()) / "jplearn-web-e2e-docker.json"


def up() -> int:
    stop_docker_postgres(PROJECT)
    url = start_docker_postgres(PROJECT, seed=True)
    STATE.write_text(json.dumps({"project": PROJECT, "databaseUrl": url}), encoding="utf-8")
    print(f"E2E_DB_READY {url}")
    return 0


def down() -> int:
    stop_docker_postgres(PROJECT)
    STATE.unlink(missing_ok=True)
    print("E2E_DB_STOPPED")
    return 0


def url() -> int:
    if not STATE.exists():
        print("no running web E2E database; run `db.py up` first", file=sys.stderr)
        return 1
    print(json.loads(STATE.read_text(encoding="utf-8"))["databaseUrl"])
    return 0


ACTIONS = {"up": up, "down": down, "url": url}


def main() -> int:
    action = ACTIONS.get(sys.argv[1] if len(sys.argv) > 1 else "up")
    if action is None:
        print("usage: python differential/db.py <up|down|url>", file=sys.stderr)
        return 2
    return action()


if __name__ == "__main__":
    sys.exit(main())
